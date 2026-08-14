//! The microphone.
//!
//! This is why the host is signed. Opening an input device is what makes macOS
//! ask, and TCC attaches its answer to a code signature -- so an unsigned
//! binary would be asked again on every rebuild.
//!
//! What comes out is what whisper wants and nothing more: 16 kHz, mono,
//! 16-bit. The device rarely offers that directly, so it is downmixed and
//! resampled here rather than shipped at 48 kHz stereo and fixed later. A
//! three-second utterance leaves as ~96 KB instead of ~576 KB, and the core
//! never has to know what a sample rate is.

use std::io::Cursor;
use std::sync::{Arc, Mutex};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};

/// What whisper.cpp expects. Anything else is resampled to it here.
pub const TARGET_RATE: u32 = 16_000;

#[derive(Debug)]
pub enum Error {
    NoDevice,
    NothingSaid,
    Unsupported(String),
    Device(String),
    Encoding(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoDevice => write!(
                formatter,
                "no input device. Check System Settings > Sound > Input"
            ),
            Self::NothingSaid => write!(formatter, "nothing was said"),
            Self::Unsupported(what) => write!(formatter, "unsupported audio: {what}"),
            Self::Device(why) => write!(
                formatter,
                "microphone unavailable: {why}. If macOS has not asked for \
                 permission, grant it in System Settings > Privacy & Security \
                 > Microphone"
            ),
            Self::Encoding(why) => write!(formatter, "could not encode audio: {why}"),
        }
    }
}

impl std::error::Error for Error {}

/// Average the channels. A microphone array recorded in stereo is still one
/// person talking, and whisper takes mono.
fn to_mono(frame: &[f32], channels: usize) -> f32 {
    if channels <= 1 {
        return frame.first().copied().unwrap_or(0.0);
    }
    frame.iter().take(channels).sum::<f32>() / channels as f32
}

/// Linear interpolation down to 16 kHz.
///
/// Not a windowed resampler: speech at 16 kHz from a 48 kHz source has
/// negligible aliasing that matters to whisper, and a proper resampler is a
/// dependency to add when something measures a difference.
fn resample(samples: &[f32], from: u32, to: u32) -> Vec<f32> {
    if from == to || samples.is_empty() {
        return samples.to_vec();
    }

    let ratio = from as f64 / to as f64;
    let count = ((samples.len() as f64) / ratio).floor() as usize;
    let mut out = Vec::with_capacity(count);

    for index in 0..count {
        let position = index as f64 * ratio;
        let left = position.floor() as usize;
        let right = (left + 1).min(samples.len() - 1);
        let weight = (position - left as f64) as f32;
        out.push(samples[left] * (1.0 - weight) + samples[right] * weight);
    }
    out
}

fn to_i16(samples: &[f32]) -> Vec<i16> {
    samples
        .iter()
        .map(|sample| (sample.clamp(-1.0, 1.0) * i16::MAX as f32) as i16)
        .collect()
}

/// A WAV in memory. It is never written to disk here: the host hands it to the
/// core, and the core deletes its copy as soon as the words are out.
pub fn to_wav(samples: &[i16]) -> Result<Vec<u8>, Error> {
    let spec = hound::WavSpec {
        channels: 1,
        sample_rate: TARGET_RATE,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };

    let mut buffer = Cursor::new(Vec::new());
    {
        let mut writer = hound::WavWriter::new(&mut buffer, spec)
            .map_err(|error| Error::Encoding(error.to_string()))?;
        for sample in samples {
            writer
                .write_sample(*sample)
                .map_err(|error| Error::Encoding(error.to_string()))?;
        }
        writer
            .finalize()
            .map_err(|error| Error::Encoding(error.to_string()))?;
    }
    Ok(buffer.into_inner())
}

/// How loud a frame is. Speech and silence differ by more than an order of
/// magnitude here, which is why a measure this crude is enough to tell them
/// apart in a quiet room.
pub fn rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum: f32 = samples.iter().map(|s| s * s).sum();
    (sum / samples.len() as f32).sqrt()
}

/// What the listener should do next.
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum Decision {
    /// Still calibrating, waiting, or listening to speech.
    Continue,
    /// Speech began and has stopped. This is the utterance.
    Done,
    /// Nobody said anything. Not an utterance, and not silence to transcribe.
    NothingSaid,
}

/// Energy-based voice activity detection.
///
/// The threshold is relative to the room, not absolute: a fixed number works
/// in one kitchen and fails in the next. The first fraction of a second is
/// spent listening to the room, and speech is what stands well above it.
///
/// This is honest about what it is. It will treat loud music or a nearby
/// conversation as speech, because by this measure they are. A model-based
/// VAD is the answer when that becomes the problem, and it is a model to load
/// and a dependency to carry, so it waits until something measures the need.
#[derive(Debug)]
pub struct Vad {
    pub calibration: f32,
    pub silence_hold: f32,
    pub max_wait: f32,
    pub max_length: f32,
    floor: f32,
    frames: u32,
    elapsed: f32,
    speaking: bool,
    quiet_for: f32,
    started_at: f32,
}

impl Default for Vad {
    fn default() -> Self {
        Self {
            // Long enough to hear the room, short enough that nobody notices.
            calibration: 0.3,
            // A pause inside a sentence is shorter than this; the end of one
            // is longer. Too short cuts people off mid-thought, which is worse
            // than waiting.
            silence_hold: 0.8,
            // Nothing said in five seconds means nothing is going to be.
            max_wait: 5.0,
            // A cap, not a target: a stuck microphone must not record forever.
            max_length: 20.0,
            floor: 0.0,
            frames: 0,
            elapsed: 0.0,
            speaking: false,
            quiet_for: 0.0,
            started_at: 0.0,
        }
    }
}

impl Vad {
    /// Feed one frame's loudness and its duration.
    pub fn observe(&mut self, level: f32, seconds: f32) -> Decision {
        self.elapsed += seconds;

        if self.elapsed <= self.calibration {
            // Listening to the room. A running mean rather than a peak: one
            // door closing should not deafen the whole utterance.
            self.frames += 1;
            self.floor += (level - self.floor) / self.frames as f32;
            return Decision::Continue;
        }

        let threshold = (self.floor * 4.0).max(0.01);

        if level > threshold {
            if !self.speaking {
                self.speaking = true;
                self.started_at = self.elapsed;
            }
            self.quiet_for = 0.0;
        } else if self.speaking {
            self.quiet_for += seconds;
            if self.quiet_for >= self.silence_hold {
                return Decision::Done;
            }
        } else if self.elapsed - self.calibration >= self.max_wait {
            return Decision::NothingSaid;
        }

        if self.speaking && self.elapsed - self.started_at >= self.max_length {
            return Decision::Done;
        }

        Decision::Continue
    }
}

/// Record until `stop` returns. `stop` blocks -- it is the push-to-talk
/// gesture, and in a terminal that gesture is a keypress.
pub fn record(stop: impl FnOnce()) -> Result<Vec<i16>, Error> {
    let capture = open()?;
    stop();
    capture.finish()
}

/// Listen until told to stop, handing over each utterance as it ends.
///
/// The device is opened once and stays open, which is what makes this a wake
/// loop rather than a series of recordings: opening the microphone for every
/// burst of speech would flicker the system's own indicator all day and pay
/// the device's start-up cost each time.
///
/// `heard` is given the samples of one utterance and answers whether to keep
/// listening. Silence produces nothing at all -- the room is not an utterance,
/// and a wake loop that reported every quiet second would be a busy loop with
/// a microphone attached.
pub fn listen(
    make: impl Fn() -> Vad,
    mut heard: impl FnMut(Vec<i16>) -> bool,
) -> Result<(), Error> {
    let capture = open()?;
    let frame = std::time::Duration::from_millis(50);
    let seconds = frame.as_secs_f32();
    let mut vad = make();
    let mut consumed = 0usize;
    let mut utterance: Vec<f32> = Vec::new();

    loop {
        std::thread::sleep(frame);

        let (level, fresh) = {
            let buffer = capture
                .collected
                .lock()
                .map_err(|_| Error::Device("the capture thread panicked".into()))?;
            let fresh = buffer[consumed.min(buffer.len())..].to_vec();
            consumed = buffer.len();
            (rms(&fresh), fresh)
        };

        utterance.extend_from_slice(&fresh);

        match vad.observe(level, seconds) {
            Decision::Continue => {}
            Decision::Done => {
                let samples = to_i16(&resample(&utterance, capture.rate, TARGET_RATE));
                utterance.clear();
                vad = make();
                if !heard(samples) {
                    return Ok(());
                }
            }
            Decision::NothingSaid => {
                // A quiet stretch. Not an error here, unlike a single
                // recording: quiet is what a room is most of the time.
                utterance.clear();
                vad = make();
            }
        }
    }
}

/// Record until the room goes quiet again.
///
/// Polls the buffer rather than deciding inside the audio callback: the
/// callback runs on a realtime thread, and the less it does the fewer glitches
/// there are. A few milliseconds of latency on the decision costs nothing --
/// the silence being waited for is measured in hundreds.
pub fn record_until_silence(mut vad: Vad) -> Result<Vec<i16>, Error> {
    let capture = open()?;
    let frame = std::time::Duration::from_millis(50);
    let seconds = frame.as_secs_f32();
    let mut consumed = 0usize;

    loop {
        std::thread::sleep(frame);

        let level = {
            let buffer = capture
                .collected
                .lock()
                .map_err(|_| Error::Device("the capture thread panicked".into()))?;
            let fresh = &buffer[consumed.min(buffer.len())..];
            let level = rms(fresh);
            consumed = buffer.len();
            level
        };

        match vad.observe(level, seconds) {
            Decision::Continue => {}
            Decision::Done => return capture.finish(),
            Decision::NothingSaid => {
                // Deliberately not an empty recording: silence sent onward
                // would be transcribed into whatever whisper hallucinates
                // from a quiet room.
                drop(capture);
                return Err(Error::NothingSaid);
            }
        }
    }
}

struct Capture {
    stream: cpal::Stream,
    collected: Arc<Mutex<Vec<f32>>>,
    faults: Arc<Mutex<Option<String>>>,
    rate: u32,
}

impl Capture {
    fn finish(self) -> Result<Vec<i16>, Error> {
        drop(self.stream);

        if let Some(fault) = self.faults.lock().ok().and_then(|slot| slot.clone()) {
            return Err(Error::Device(fault));
        }

        let captured = self
            .collected
            .lock()
            .map_err(|_| Error::Device("the capture thread panicked".into()))?
            .clone();

        Ok(to_i16(&resample(&captured, self.rate, TARGET_RATE)))
    }
}

fn open() -> Result<Capture, Error> {
    let host = cpal::default_host();
    let device = host.default_input_device().ok_or(Error::NoDevice)?;
    let supported = device
        .default_input_config()
        .map_err(|error| Error::Device(error.to_string()))?;

    let rate = supported.sample_rate().0;
    let channels = supported.channels() as usize;
    let config: StreamConfig = supported.config();
    let format = supported.sample_format();

    let collected = Arc::new(Mutex::new(Vec::<f32>::new()));
    let sink = Arc::clone(&collected);
    let faults = Arc::new(Mutex::new(Option::<String>::None));
    let fault_sink = Arc::clone(&faults);

    let on_error = move |error: cpal::StreamError| {
        if let Ok(mut slot) = fault_sink.lock() {
            slot.get_or_insert(error.to_string());
        }
    };

    let stream = match format {
        SampleFormat::F32 => device.build_input_stream(
            &config,
            move |data: &[f32], _: &_| {
                if let Ok(mut buffer) = sink.lock() {
                    buffer.extend(data.chunks(channels).map(|f| to_mono(f, channels)));
                }
            },
            on_error,
            None,
        ),
        SampleFormat::I16 => device.build_input_stream(
            &config,
            move |data: &[i16], _: &_| {
                if let Ok(mut buffer) = sink.lock() {
                    buffer.extend(data.chunks(channels).map(|frame| {
                        let as_float: Vec<f32> =
                            frame.iter().map(|s| *s as f32 / i16::MAX as f32).collect();
                        to_mono(&as_float, channels)
                    }));
                }
            },
            on_error,
            None,
        ),
        other => return Err(Error::Unsupported(format!("{other:?} samples"))),
    }
    .map_err(|error| Error::Device(error.to_string()))?;

    stream
        .play()
        .map_err(|error| Error::Device(error.to_string()))?;

    Ok(Capture {
        stream,
        collected,
        faults,
        rate,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Feed a Vad a sequence of levels at 50 ms a frame.
    fn run(vad: &mut Vad, levels: &[f32]) -> Decision {
        for level in levels {
            match vad.observe(*level, 0.05) {
                Decision::Continue => {}
                other => return other,
            }
        }
        Decision::Continue
    }

    fn quiet(seconds: f32) -> Vec<f32> {
        vec![0.001; (seconds / 0.05) as usize]
    }

    fn speech(seconds: f32) -> Vec<f32> {
        vec![0.2; (seconds / 0.05) as usize]
    }

    #[test]
    fn silence_after_speech_ends_the_utterance() {
        let mut vad = Vad::default();
        let mut levels = quiet(0.3); // the room
        levels.extend(speech(1.0)); // someone talking
        levels.extend(quiet(1.0)); // and stopping

        assert_eq!(run(&mut vad, &levels), Decision::Done);
    }

    #[test]
    fn a_pause_inside_a_sentence_does_not_end_it() {
        // Half a second of thinking is not the end of a sentence. Cutting
        // someone off mid-thought is worse than waiting a moment longer.
        let mut vad = Vad::default();
        let mut levels = quiet(0.3);
        levels.extend(speech(0.5));
        levels.extend(quiet(0.5));
        levels.extend(speech(0.5));

        assert_eq!(run(&mut vad, &levels), Decision::Continue);
    }

    #[test]
    fn a_quiet_room_is_not_an_utterance() {
        // Sending silence onward would have whisper hallucinate something out
        // of a fan.
        let mut vad = Vad::default();

        assert_eq!(run(&mut vad, &quiet(6.0)), Decision::NothingSaid);
    }

    #[test]
    fn the_threshold_is_relative_to_the_room() {
        // The same speech level in a loud room is not speech. A fixed
        // threshold works in one kitchen and fails in the next.
        // A room with a fan: the fan is the floor, so the fan is not speech,
        // and five seconds of it is nothing said.
        let mut noisy = Vad::default();
        let fan = vec![0.05; 6 + 120];
        assert_eq!(run(&mut noisy, &fan), Decision::NothingSaid);

        // The same level in a quiet room is somebody talking, so it ends the
        // way an utterance ends: with silence after it.
        let mut still = Vad::default();
        let mut louder = quiet(0.3);
        louder.extend(vec![0.05; 20]);
        louder.extend(quiet(1.0));
        assert_eq!(run(&mut still, &louder), Decision::Done);
    }

    #[test]
    fn a_stuck_microphone_does_not_record_forever() {
        let mut vad = Vad {
            max_length: 1.0,
            ..Vad::default()
        };
        let mut levels = quiet(0.3);
        levels.extend(speech(5.0));

        assert_eq!(run(&mut vad, &levels), Decision::Done);
    }

    #[test]
    fn loudness_is_the_root_mean_square() {
        assert_eq!(rms(&[]), 0.0);
        assert_eq!(rms(&[1.0, -1.0]), 1.0);
        assert!(rms(&[0.0, 0.0]) < 1e-9);
    }

    #[test]
    fn stereo_is_averaged_into_one_voice() {
        assert_eq!(to_mono(&[1.0, 0.0], 2), 0.5);
        assert_eq!(to_mono(&[0.5], 1), 0.5);
    }

    #[test]
    fn resampling_48k_to_16k_keeps_a_third_of_the_samples() {
        let input: Vec<f32> = (0..48_000).map(|i| i as f32 / 48_000.0).collect();

        let output = resample(&input, 48_000, 16_000);

        assert_eq!(output.len(), 16_000);
        // A ramp stays a ramp: the first and last samples survive intact.
        assert!((output[0] - 0.0).abs() < 1e-6);
        assert!(output[15_999] > 0.99);
    }

    #[test]
    fn a_matching_rate_is_left_alone() {
        let input = vec![0.1, 0.2, 0.3];

        assert_eq!(resample(&input, 16_000, 16_000), input);
    }

    #[test]
    fn full_scale_maps_to_full_scale() {
        assert_eq!(to_i16(&[1.0, -1.0, 0.0]), vec![i16::MAX, -i16::MAX, 0]);
        // Anything louder than full scale clips rather than wrapping, which
        // would turn a shout into a different sound entirely.
        assert_eq!(to_i16(&[2.0, -2.0]), vec![i16::MAX, -i16::MAX]);
    }

    #[test]
    fn the_wav_says_what_whisper_expects() {
        let wav = to_wav(&[0, 1, -1]).expect("wav");

        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        // 16 kHz, mono, 16-bit, little-endian in the fmt chunk.
        assert_eq!(u16::from_le_bytes([wav[22], wav[23]]), 1);
        assert_eq!(
            u32::from_le_bytes([wav[24], wav[25], wav[26], wav[27]]),
            TARGET_RATE
        );
        assert_eq!(u16::from_le_bytes([wav[34], wav[35]]), 16);
    }
}
