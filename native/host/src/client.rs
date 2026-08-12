//! Talking to the Python daemon over its Unix socket.
//!
//! This is the second reader of `protocol/generated/ev.schema.json`, and the
//! point of the artifact: if the daemon's framing, correlation or handshake
//! were only self-consistent, this is where that would show.
//!
//! Blocking on purpose. The host does one conversation per turn, and an async
//! runtime would be a dependency with nothing to run until audio arrives.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;

use serde_json::{json, Value};

use crate::protocol::{ConfirmationRequired, Response, SpeechRequested};

/// The version this host speaks. A mismatch is refused by the daemon, and
/// refusing is the point: a protocol neither side agrees on is not a
/// conversation worth having.
pub const PROTOCOL_VERSION: &str = "1.2";

#[derive(Debug)]
pub enum Error {
    Unavailable(String),
    Refused(String),
    Io(std::io::Error),
    Malformed(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unavailable(path) => {
                write!(formatter, "no daemon at {path}. Start one with: ev --serve")
            }
            Self::Refused(why) => write!(formatter, "the daemon refused: {why}"),
            Self::Io(error) => write!(formatter, "socket error: {error}"),
            Self::Malformed(line) => write!(formatter, "unreadable line: {line}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

/// What a turn produced: the events it emitted, then its response.
///
/// Typed with the generated structs rather than raw JSON, which is the whole
/// point of the committed schema: if the daemon's shapes and these disagree,
/// this fails to deserialise instead of quietly reading the wrong field.
#[derive(Debug)]
pub struct Turn {
    /// What the core heard, when the turn began as speech.
    pub heard: Option<String>,
    pub speech: Vec<SpeechRequested>,
    pub response: Response,
}

#[derive(Debug)]
pub struct Client {
    stream: UnixStream,
    reader: BufReader<UnixStream>,
    counter: u64,
}

impl Client {
    /// Connect and shake hands. Nothing else is served until that succeeds.
    pub fn connect(path: &Path) -> Result<Self, Error> {
        let stream = UnixStream::connect(path)
            .map_err(|_| Error::Unavailable(path.display().to_string()))?;
        let reader = BufReader::new(stream.try_clone()?);

        let mut client = Self {
            stream,
            reader,
            counter: 0,
        };
        client.hello()?;
        Ok(client)
    }

    fn hello(&mut self) -> Result<(), Error> {
        let response = self.request(json!({
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "client": "ev-host",
        }))?;

        if !response.ok {
            let why = response
                .error
                .map(|error| error.message)
                .unwrap_or_else(|| "no reason given".to_string());
            return Err(Error::Refused(why));
        }
        Ok(())
    }

    fn next_id(&mut self) -> String {
        self.counter += 1;
        format!("h{}", self.counter)
    }

    fn write(&mut self, id: &str, command: Value) -> Result<(), Error> {
        let line = serde_json::to_string(&json!({ "id": id, "command": command }))
            .map_err(|error| Error::Malformed(error.to_string()))?;
        // One message per line: the framing is the newline, so the payload
        // must not contain one. serde_json::to_string does not emit any.
        self.stream.write_all(line.as_bytes())?;
        self.stream.write_all(b"\n")?;
        self.stream.flush()?;
        Ok(())
    }

    fn read(&mut self) -> Result<Value, Error> {
        let mut line = String::new();
        if self.reader.read_line(&mut line)? == 0 {
            return Err(Error::Unavailable("the daemon closed".to_string()));
        }
        serde_json::from_str(&line).map_err(|_| Error::Malformed(line))
    }

    /// Send one command and read until its response. Anything arriving first
    /// is an event, and events are not answers.
    fn request(&mut self, command: Value) -> Result<Response, Error> {
        let id = self.next_id();
        self.write(&id, command)?;

        loop {
            let message = self.read()?;
            // Events carry `type`; responses carry `id`, `ok` and `payload`.
            // Matching on the id alone is ambiguous, because
            // confirmation.required has an `id` of its own.
            if message.get("type").is_none() && message["id"] == json!(id) {
                return serde_json::from_value(message)
                    .map_err(|error| Error::Malformed(error.to_string()));
            }
        }
    }

    /// One turn from typed text.
    pub fn submit(
        &mut self,
        text: &str,
        locale: Option<&str>,
        answer: &mut dyn FnMut(&Value) -> bool,
    ) -> Result<Turn, Error> {
        self.turn(
            json!({ "type": "utterance.submit", "text": text, "locale": locale }),
            answer,
        )
    }

    /// One turn from recorded speech. The core transcribes and then routes
    /// exactly as if the words had been typed, so everything after this point
    /// is identical -- including what is journalled.
    pub fn submit_audio(
        &mut self,
        wav: &[u8],
        locale: Option<&str>,
        answer: &mut dyn FnMut(&Value) -> bool,
    ) -> Result<Turn, Error> {
        use base64::Engine as _;
        let encoded = base64::engine::general_purpose::STANDARD.encode(wav);
        self.turn(
            json!({ "type": "audio.submit", "audio": encoded, "locale": locale }),
            answer,
        )
    }

    /// One turn from one frame. The core answers about what is in it and acts
    /// on nothing it was not asked to: `vision.look` has no argument that
    /// selects a target, which is the whole design (ADR 0029).
    ///
    /// `text` is what was said while looking. `None` means: describe it.
    pub fn submit_vision(
        &mut self,
        image: &[u8],
        text: Option<&str>,
        locale: Option<&str>,
        answer: &mut dyn FnMut(&Value) -> bool,
    ) -> Result<Turn, Error> {
        use base64::Engine as _;
        let encoded = base64::engine::general_purpose::STANDARD.encode(image);
        self.turn(
            json!({
                "type": "vision.submit",
                "image": encoded,
                "text": text,
                "locale": locale,
            }),
            answer,
        )
    }

    /// `answer` decides confirmations; the host does not decide them itself,
    /// which is the same rule the CLI follows.
    fn turn(
        &mut self,
        command: Value,
        answer: &mut dyn FnMut(&Value) -> bool,
    ) -> Result<Turn, Error> {
        let id = self.next_id();
        self.write(&id, command)?;

        let mut speech = Vec::new();
        let mut heard = None;

        loop {
            let message = self.read()?;

            if message.get("type").is_none() && message["id"] == json!(id) {
                let response = serde_json::from_value(message)
                    .map_err(|error| Error::Malformed(error.to_string()))?;
                return Ok(Turn {
                    heard,
                    speech,
                    response,
                });
            }

            // Dispatch on the discriminator rather than on shape. The
            // generated unions are untagged, and matching by field shape is
            // one same-shaped message away from reading the wrong type.
            match message["type"].as_str() {
                Some("confirmation.required") => {
                    let asked: ConfirmationRequired = serde_json::from_value(message.clone())
                        .map_err(|error| Error::Malformed(error.to_string()))?;
                    let granted = answer(&message);
                    let reply = self.next_id();
                    self.write(
                        &reply,
                        json!({
                            "type": "confirmation.respond",
                            "request": asked.id,
                            "granted": granted,
                        }),
                    )?;
                }
                Some("transcription.partial") => {
                    // What E.V. heard, before it acts on it. Worth showing
                    // even when it is right, and especially when it is not.
                    heard = message["text"].as_str().map(str::to_string);
                }
                Some("speech.requested") => {
                    speech.push(
                        serde_json::from_value(message.clone())
                            .map_err(|error| Error::Malformed(error.to_string()))?,
                    );
                }
                _ => {}
            }
        }
    }

    /// What E.V. has done, newest first.
    ///
    /// A request with an answer: history is asked for when a panel opens, not
    /// pushed at a client that did not want it.
    ///
    /// `query` searches the trail instead of paging it. `None` is the whole
    /// trail, which is what an empty search box means.
    pub fn history(&mut self, limit: u32, query: Option<String>) -> Result<Value, Error> {
        let response = self.request(json!({
            "type": "history.query",
            "limit": limit,
            "query": query,
        }))?;

        if !response.ok {
            let why = response
                .error
                .map(|error| error.message)
                .unwrap_or_else(|| "refused".to_string());
            return Err(Error::Refused(why));
        }

        serde_json::to_value(response.payload).map_err(|error| Error::Malformed(error.to_string()))
    }
}
