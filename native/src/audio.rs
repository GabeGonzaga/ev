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

/// Record until `stop` returns. `stop` blocks -- it is the push-to-talk
/// gesture, and in a terminal that gesture is a keypress.
pub fn record(stop: impl FnOnce()) -> Result<Vec<i16>, Error> {
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

    stop();

    drop(stream);

    if let Some(fault) = faults.lock().ok().and_then(|slot| slot.clone()) {
        return Err(Error::Device(fault));
    }

    let captured = collected
        .lock()
        .map_err(|_| Error::Device("the capture thread panicked".into()))?
        .clone();

    Ok(to_i16(&resample(&captured, rate, TARGET_RATE)))
}

#[cfg(test)]
mod tests {
    use super::*;

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
