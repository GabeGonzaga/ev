//! Cross-language conformance.
//!
//! The lines below are what the Python daemon actually writes -- copied from
//! its own tests, not invented here. If the two views of the contract drift,
//! either `make protocol-check-rust` fails on the schema or these fail on the
//! payloads, and drift is the only failure mode a shared artifact has.
//!
//! The daemon is faked with a `UnixListener` rather than started for real: a
//! test that needs Python running is a test that fails on someone else's
//! machine for reasons that have nothing to do with the code.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::PathBuf;
use std::thread;

#[path = "../src/client.rs"]
mod client;

#[path = "../../protocol/generated/rust/protocol.rs"]
// Generated code is held to the generator's standards, not ours. The crate
// denies all of clippy; these are the lints the output trips, allowed here
// rather than by loosening the rules for the code we write.
#[allow(dead_code, clippy::derivable_impls, clippy::to_string_trait_impl)]
mod protocol;

use client::{Client, Error};
use serde_json::{json, Value};

/// A socket path short enough for `sockaddr_un`, which the Python side learned
/// about the hard way: 104 bytes on macOS, and the kernel's error names
/// neither the limit nor the path.
fn socket_for(name: &str) -> PathBuf {
    let path = PathBuf::from(format!("/tmp/ev-host-{name}.sock"));
    let _ = std::fs::remove_file(&path);
    path
}

/// Answers each incoming line with the next canned reply, correlating ids the
/// way the daemon does.
fn fake_daemon(listener: UnixListener, script: Vec<Value>) -> thread::JoinHandle<Vec<Value>> {
    thread::spawn(move || {
        let (stream, _) = listener.accept().expect("a client");
        let mut writer = stream.try_clone().expect("clone");
        let reader = BufReader::new(stream);
        let mut received = Vec::new();
        let mut replies = script.into_iter();

        for line in reader.lines() {
            let line = line.expect("a line");
            let request: Value = serde_json::from_str(&line).expect("json");
            received.push(request.clone());

            for reply in replies.by_ref() {
                // A reply without `type` is the response and closes the
                // request; anything with one is an event, and more follow.
                let closes = reply.get("type").is_none();
                let filled = if closes {
                    let mut filled = reply.clone();
                    filled["id"] = request["id"].clone();
                    filled
                } else {
                    reply
                };
                writer
                    .write_all(format!("{filled}\n").as_bytes())
                    .expect("write");
                writer.flush().expect("flush");
                if closes {
                    break;
                }
            }
        }
        received
    })
}

fn accepted() -> Value {
    json!({"id": "", "ok": true, "payload": {"protocol": "1.1"}})
}

#[test]
fn a_handshake_is_sent_before_anything_else() {
    let path = socket_for("handshake");
    let listener = UnixListener::bind(&path).expect("bind");
    let daemon = fake_daemon(listener, vec![accepted()]);

    let client = Client::connect(&path).expect("connect");
    drop(client);

    let received = daemon.join().expect("join");
    assert_eq!(received[0]["command"]["type"], json!("hello"));
    assert_eq!(received[0]["command"]["protocol"], json!("1.1"));
    let _ = std::fs::remove_file(&path);
}

#[test]
fn a_refused_handshake_is_reported() {
    let path = socket_for("refused");
    let listener = UnixListener::bind(&path).expect("bind");
    let daemon = fake_daemon(
        listener,
        vec![json!({
            "id": "",
            "ok": false,
            "error": {"code": "protocol_mismatch", "message": "this daemon speaks 1.1"}
        })],
    );

    let error = Client::connect(&path).expect_err("refusal");

    assert!(matches!(error, Error::Refused(ref why) if why.contains("speaks 1.1")));
    let _ = daemon.join();
    let _ = std::fs::remove_file(&path);
}

#[test]
fn the_daemons_own_payloads_deserialise() {
    // Verbatim from the Python daemon's tests: a turn emits tool.completed,
    // speech.requested and state.changed, then answers.
    let path = socket_for("turn");
    let listener = UnixListener::bind(&path).expect("bind");
    let daemon = fake_daemon(
        listener,
        vec![
            accepted(),
            json!({"type": "tool.completed", "tool": "browser.open_url", "ok": true,
                   "speech": "Opening github.com", "error": null}),
            json!({"type": "speech.requested", "text": "Opening github.com",
                   "voice": "pt-PT", "interrupt": false}),
            json!({"type": "state.changed", "state": "idle"}),
            json!({"id": "", "ok": true,
                   "payload": {"outcome": "ran", "ok": true, "tool": "browser.open_url"}}),
        ],
    );

    let mut client = Client::connect(&path).expect("connect");
    let turn = client
        .submit("open github.com", Some("pt-PT"), &mut |_| true)
        .expect("turn");

    assert_eq!(turn.speech.len(), 1);
    assert_eq!(turn.speech[0].text, "Opening github.com");
    assert_eq!(turn.speech[0].voice, "pt-PT");
    assert!(turn.response.ok);
    assert_eq!(turn.response.payload["outcome"], json!("ran"));

    drop(client);
    let _ = daemon.join();
    let _ = std::fs::remove_file(&path);
}

#[test]
fn a_confirmation_is_answered_by_the_caller_not_the_client() {
    let path = socket_for("confirm");
    let listener = UnixListener::bind(&path).expect("bind");
    let daemon = fake_daemon(
        listener,
        vec![
            accepted(),
            json!({"type": "confirmation.required", "id": "c1",
                   "tool": "system.empty_trash", "risk": "destructive",
                   "arguments": {"count": 3}}),
            json!({"id": "", "ok": true, "payload": {"outcome": "ran", "ok": false}}),
        ],
    );

    let mut asked: Vec<String> = Vec::new();
    let mut client = Client::connect(&path).expect("connect");
    let turn = client
        .submit("empty the trash", None, &mut |event| {
            asked.push(event["tool"].as_str().unwrap_or_default().to_string());
            false
        })
        .expect("turn");

    assert_eq!(asked, vec!["system.empty_trash"]);
    assert!(turn.response.ok);

    drop(client);
    let received = daemon.join().expect("join");
    // The answer goes back as its own command, correlated to the event's id.
    let answer = received
        .iter()
        .find(|message| message["command"]["type"] == json!("confirmation.respond"))
        .expect("an answer was sent");
    assert_eq!(answer["command"]["request"], json!("c1"));
    assert_eq!(answer["command"]["granted"], json!(false));
    let _ = std::fs::remove_file(&path);
}

#[test]
fn a_missing_daemon_says_how_to_start_one() {
    let error =
        Client::connect(&PathBuf::from("/tmp/ev-host-nothing-here.sock")).expect_err("no daemon");

    assert!(format!("{error}").contains("ev --serve"));
}

#[test]
fn a_stream_that_closes_is_not_a_hang() {
    let path = socket_for("closes");
    let listener = UnixListener::bind(&path).expect("bind");
    thread::spawn(move || {
        let (stream, _) = listener.accept().expect("a client");
        drop(stream);
    });

    let error = Client::connect(&path).expect_err("closed");

    // Either the write or the read notices, depending on timing. Both are
    // "the daemon is not there", and neither is a hang.
    assert!(matches!(error, Error::Unavailable(_) | Error::Io(_)));
    let _ = std::fs::remove_file(&path);
}

#[test]
fn the_length_constraint_crossed_the_boundary() {
    // `text` is min 1, max 4000 in the Python model, and the generated Rust
    // carries the same bound. One declaration, two languages.
    use std::str::FromStr;

    assert!(protocol::Text::from_str("abre example.com").is_ok());
    assert!(protocol::Text::from_str("").is_err());
    assert!(protocol::Text::from_str(&"x".repeat(4001)).is_err());
}

#[allow(dead_code)]
fn unused(_: UnixStream) {}
