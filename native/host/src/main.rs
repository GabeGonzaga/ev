//! The native host skeleton.
//!
//! What it is today: the signed process that speaks the protocol. That is
//! deliberately all of it. TCC-facing capabilities -- microphone, camera,
//! Accessibility, Apple Events -- belong here eventually, and none of them are
//! here yet, because each needs a decision that has not been made.
//!
//! Signing matters now rather than later: TCC keys its grants to a code
//! signature, so an unsigned host is re-prompted on every rebuild and can
//! never hold a stable permission.
//!
//!     ev-host "abre example.com"
//!     ev-host --socket /tmp/ev/ev.sock "open github.com"

use std::io::{self, Write};
use std::path::PathBuf;
use std::process::{Command, ExitCode};

use serde_json::Value;

use ev_host::audio;
use ev_host::client::{Client, Error};

const EXIT_FAILED: u8 = 1;
const EXIT_NOT_UNDERSTOOD: u8 = 2;
const EXIT_UNSURE: u8 = 3;
const EXIT_UNAVAILABLE: u8 = 4;

fn default_socket() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home)
        .join("Library/Application Support/EV")
        .join("ev.sock")
}

/// Ask on the terminal. Anything other than an explicit yes is a no, and a
/// stdin that is not a terminal is not consent.
fn ask(event: &Value) -> bool {
    let tool = event["tool"].as_str().unwrap_or("?");
    let risk = event["risk"].as_str().unwrap_or("?");
    eprintln!("{tool} ({risk}) {}", event["arguments"]);

    let mut answer = String::new();
    if io::stdin().read_line(&mut answer).unwrap_or(0) == 0 {
        eprintln!("declined: nothing answered");
        return false;
    }

    matches!(
        answer.trim().to_lowercase().as_str(),
        "y" | "yes" | "s" | "sim"
    )
}

/// The pt-PT voice. Without naming her, macOS reads a Portuguese sentence
/// with whatever the system default is, which is usually Brazilian or English.
fn voice_for(locale: &str) -> Option<&'static str> {
    match locale {
        "pt-PT" => Some("Joana"),
        _ => None,
    }
}

/// Speaking is the host's job because the audio device is the host's. `say` is
/// the development engine; AVSpeechSynthesizer replaces it in the application,
/// and nothing on the Python side changes when it does.
fn speak(text: &str, locale: &str) {
    let mut command = Command::new("say");
    if let Some(voice) = voice_for(locale) {
        command.arg("-v").arg(voice);
    }
    // "--" ends option parsing: a sentence starting with "-" is a sentence.
    command.arg("--").arg(text);

    if let Err(error) = command.status() {
        // Failing to speak is not a reason to fail a turn that already
        // happened. The words are on screen either way.
        eprintln!("could not speak: {error}");
    }
}

/// Push-to-talk, as a terminal can express it: recording starts, and the
/// keypress that ends it is the release. A global hotkey needs an event tap
/// and an Accessibility grant, which is phase 3's problem.
fn listen(locale: Option<&str>, vad: bool) -> Result<Vec<u8>, audio::Error> {
    let samples = if vad {
        eprintln!("listening... speak, and stop when you are done");
        audio::record_until_silence(audio::Vad::default())?
    } else {
        eprintln!("listening... press Enter to stop");
        audio::record(|| {
            let mut line = String::new();
            let _ = io::stdin().read_line(&mut line);
        })?
    };

    let seconds = samples.len() as f32 / audio::TARGET_RATE as f32;
    eprintln!("heard {seconds:.1}s");
    let _ = locale;
    audio::to_wav(&samples)
}

fn run(
    socket: PathBuf,
    utterance: String,
    aloud: bool,
    listening: bool,
    vad: bool,
    locale: Option<String>,
) -> Result<u8, Error> {
    let mut client = Client::connect(&socket)?;

    let turn = if listening {
        let wav = match listen(locale.as_deref(), vad) {
            Ok(wav) => wav,
            Err(error) => {
                eprintln!("{error}");
                return Ok(EXIT_FAILED);
            }
        };
        client.submit_audio(&wav, locale.as_deref(), &mut ask)?
    } else {
        client.submit(&utterance, locale.as_deref(), &mut ask)?
    };

    if let Some(heard) = &turn.heard {
        // Printed even when it is right: being misheard should be visible in
        // the words, not inferred from the wrong thing happening.
        eprintln!("heard: {heard}");
    }

    for spoken in &turn.speech {
        // speech.requested is the daemon asking for a sentence to be spoken.
        // It crosses as intent -- a sentence and a voice -- and the host turns
        // it into sound.
        println!("{}", spoken.text);
        if aloud {
            speak(&spoken.text, &spoken.voice);
        }
    }

    // A refusal from the daemon -- nothing was said, transcription failed, a
    // tool was denied -- has a reason. Printing the exit code alone and
    // swallowing the sentence is how a failure becomes a mystery.
    if let Some(error) = &turn.response.error {
        eprintln!("{}", error.message);
    }

    let payload = &turn.response.payload;
    Ok(match payload.get("outcome").and_then(Value::as_str) {
        Some("not_understood") => {
            eprintln!("I did not understand that.");
            EXIT_NOT_UNDERSTOOD
        }
        Some("unsure") => EXIT_UNSURE,
        _ if payload.get("ok").and_then(Value::as_bool) == Some(true) => 0,
        _ => EXIT_FAILED,
    })
}

fn main() -> ExitCode {
    let mut arguments = std::env::args().skip(1);
    let mut socket = default_socket();
    let mut words: Vec<String> = Vec::new();
    let mut aloud = false;
    let mut listening = false;
    let mut vad = false;
    let mut locale: Option<String> = None;

    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "--speak" => aloud = true,
            "--listen" => listening = true,
            // Push-to-talk first, VAD second: CLAUDE.md's order, and the
            // keypress stays because it is the one that always works.
            "--vad" => {
                listening = true;
                vad = true;
            }
            "--locale" => locale = arguments.next(),
            "--socket" => match arguments.next() {
                Some(path) => socket = PathBuf::from(path),
                None => {
                    eprintln!("--socket needs a path");
                    return ExitCode::from(EXIT_FAILED);
                }
            },
            _ => words.push(argument),
        }
    }

    if words.is_empty() && !listening {
        eprintln!(
            "usage: ev-host [--socket PATH] [--locale TAG] [--speak] \
             [--listen | --vad | <utterance>]"
        );
        return ExitCode::from(EXIT_NOT_UNDERSTOOD);
    }

    let _ = io::stdout().flush();
    match run(socket, words.join(" "), aloud, listening, vad, locale) {
        Ok(code) => ExitCode::from(code),
        Err(error @ Error::Unavailable(_)) => {
            eprintln!("{error}");
            ExitCode::from(EXIT_UNAVAILABLE)
        }
        Err(error) => {
            eprintln!("{error}");
            ExitCode::from(EXIT_FAILED)
        }
    }
}
