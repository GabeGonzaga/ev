//! The camera. One frame, then off again.
//!
//! This is the other half of why the host is signed: opening a camera is what
//! makes macOS ask, and TCC attaches its answer to a code signature.
//!
//! `CLAUDE.md` invariant 8 asks for four things -- explicit permission, a
//! visible active state, a session timeout, and frames that are not persisted.
//! Three of them are here. The session is a single frame with a hard deadline,
//! the bytes are returned rather than written anywhere, and permission is
//! asked for by name. The visible part belongs to the window, which is what
//! `camera.started` and `camera.stopped` are for.
//!
//! macOS only. On Linux the host has no camera to open and the app that would
//! use it does not exist.

use std::sync::mpsc;
use std::time::Duration;

use image::codecs::jpeg::JpegEncoder;
use image::{ColorType, ImageEncoder};
use nokhwa::pixel_format::RgbFormat;
use nokhwa::utils::{CameraIndex, RequestedFormat, RequestedFormatType};
use nokhwa::Camera;

/// How long the whole session may last, opening included.
///
/// A camera that never produces a frame -- in use by another application,
/// asleep, or waiting on a permission dialog nobody answered -- must not hold
/// the light on while a thread waits forever.
pub const SESSION: Duration = Duration::from_secs(10);

/// Frames to take before keeping one. A camera's first frames are black or
/// mid-exposure while the sensor wakes up, and a black frame described
/// confidently is worse than a slow one.
const WARMUP: usize = 4;

/// How much of the picture to keep. 0.8 is indistinguishable to a model and
/// about a third the bytes of 1.0 across the socket.
const QUALITY: u8 = 80;

#[derive(Debug)]
pub enum Error {
    NoDevice,
    Denied,
    Timeout,
    Device(String),
    Encoding(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoDevice => write!(
                formatter,
                "no camera. Check System Settings > Privacy & Security > Camera"
            ),
            Self::Denied => write!(
                formatter,
                "the camera was refused. System Settings > Privacy & Security > Camera"
            ),
            Self::Timeout => write!(formatter, "the camera did not produce a frame"),
            Self::Device(why) => write!(formatter, "camera: {why}"),
            Self::Encoding(why) => write!(formatter, "could not encode the frame: {why}"),
        }
    }
}

impl std::error::Error for Error {}

/// Ask macOS for the camera, once, at startup.
///
/// Permission is requested by name and before anything needs it, so the
/// dialog arrives when the person opened the app rather than in the middle of
/// a turn. `granted` says what they answered.
pub fn request(granted: impl Fn(bool) + Send + Sync + 'static) {
    // AVFoundation calls back on its own queue, which is why this is `Fn` and
    // `Sync` rather than the once-and-done shape it reads like.
    nokhwa::nokhwa_initialize(granted);
}

/// Whether macOS has already said yes.
pub fn granted() -> bool {
    nokhwa::nokhwa_check()
}

/// One frame, as JPEG bytes.
///
/// The camera is opened, warmed, read and closed inside one call. There is no
/// handle to leave open and nothing to remember to stop: a session that cannot
/// outlive the function that started it cannot be left running by a bug
/// somewhere else.
///
/// The work happens on its own thread so the deadline is real. A blocking read
/// from a device that has stopped answering is not interruptible, so the
/// thread is left to finish and drop the camera on its own while the caller is
/// told the truth.
pub fn take_frame(within: Duration) -> Result<Vec<u8>, Error> {
    bounded(within, capture)
}

/// Run `work` on its own thread and give up on it after `within`.
///
/// Giving up is all that happens: the thread is not killed, because a device
/// read that has stopped answering cannot be interrupted and a half-closed
/// camera is worse than a slow one. It finishes whenever it finishes, drops
/// the camera, and its answer goes nowhere.
fn bounded<T: Send + 'static>(
    within: Duration,
    work: impl FnOnce() -> Result<T, Error> + Send + 'static,
) -> Result<T, Error> {
    let (done, ready) = mpsc::channel();

    std::thread::spawn(move || {
        let _ = done.send(work());
    });

    ready.recv_timeout(within).unwrap_or(Err(Error::Timeout))
}

fn capture() -> Result<Vec<u8>, Error> {
    if !granted() {
        return Err(Error::Denied);
    }

    let format = RequestedFormat::new::<RgbFormat>(RequestedFormatType::AbsoluteHighestResolution);
    let mut camera = Camera::new(CameraIndex::Index(0), format).map_err(open_failed)?;
    camera.open_stream().map_err(open_failed)?;

    let mut kept = None;
    for _ in 0..=WARMUP {
        kept = Some(
            camera
                .frame()
                .map_err(|error| Error::Device(error.to_string()))?,
        );
    }

    // Explicit, and then dropped anyway: the light going out is the visible
    // half of "the session is over", and it should not wait for a destructor.
    let _ = camera.stop_stream();
    drop(camera);

    let buffer = kept.ok_or(Error::Timeout)?;
    let decoded = buffer
        .decode_image::<RgbFormat>()
        .map_err(|error| Error::Encoding(error.to_string()))?;

    let mut jpeg = Vec::new();
    JpegEncoder::new_with_quality(&mut jpeg, QUALITY)
        .write_image(
            decoded.as_raw(),
            decoded.width(),
            decoded.height(),
            ColorType::Rgb8.into(),
        )
        .map_err(|error| Error::Encoding(error.to_string()))?;

    Ok(jpeg)
}

fn open_failed(error: nokhwa::NokhwaError) -> Error {
    let said = error.to_string();
    if said.contains("Could not find") || said.contains("no device") {
        return Error::NoDevice;
    }
    Error::Device(said)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_frame_that_arrives_in_time_is_the_answer() {
        let taken = bounded(Duration::from_secs(1), || Ok(vec![1u8, 2, 3]));

        assert!(matches!(taken, Ok(frame) if frame == vec![1, 2, 3]));
    }

    #[test]
    fn a_camera_that_does_not_answer_stops_being_waited_for() {
        // The failure this exists for: a device in use by another application,
        // or a permission dialog nobody answered. The light must not stay on
        // while a thread waits forever.
        let taken = bounded(Duration::from_millis(20), || {
            std::thread::sleep(Duration::from_secs(5));
            Ok(vec![0u8])
        });

        assert!(matches!(taken, Err(Error::Timeout)));
    }

    #[test]
    fn the_session_is_bounded_and_short() {
        assert!(SESSION > Duration::ZERO && SESSION <= Duration::from_secs(30));
    }

    #[test]
    fn the_refusals_say_where_to_go() {
        // A camera that says "denied" and nothing else is a camera the person
        // has to guess about.
        assert!(Error::Denied.to_string().contains("System Settings"));
        assert!(Error::NoDevice.to_string().contains("System Settings"));
    }
}
