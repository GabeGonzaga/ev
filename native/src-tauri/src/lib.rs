//! The menu bar and the panel.
//!
//! This is the same conversation `ev-host` has, with a window around it: it
//! connects to the daemon over the same socket, speaks the same protocol, and
//! shares the client and the microphone code rather than owning copies.
//!
//! It lives in the app rather than in a helper because TCC attributes a
//! permission to the app (ADR 0019), and because a menu bar is a place to
//! show state that a terminal has nowhere to put.

mod daemon;
mod settings;
mod wake;

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use ev_host::client::{Answer, Client};
use ev_host::{audio, camera};
use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, State, WebviewWindow};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

/// The menu bar item, by name, so the core's state can be written to it later.
const TRAY: &str = "ev";

/// Matches the corner radius macOS gives its own floating panels.
const PANEL_RADIUS: f64 = 12.0;

/// Listen for E.V.'s name until told to stop.
///
/// Every burst of speech in the room goes to the core, which hears the name
/// with a small model and answers `ignored` for almost all of it. Nothing is
/// journalled and no turn is taken unless the name was said, so what this
/// loop mostly does is throw away other people's conversations (ADR 0037).
///
/// The room is heard here rather than in the core because the microphone is a
/// TCC surface and TCC belongs to the signed process -- the same reason the
/// push-to-talk path captures here.
fn wake_loop(app: AppHandle, stop: Arc<AtomicBool>) {
    let mut watching = wake::changed_at();

    while !stop.load(Ordering::Relaxed) {
        if !wake::load().enabled {
            // Switched off while running: put the microphone down and wait
            // for the file to say otherwise.
            let _ = app.emit("wake.listening", false);
            show_listening(&app, false);
            std::thread::sleep(RETRY_AFTER);
            continue;
        }

        let _ = app.emit("wake.listening", true);
        show_listening(&app, true);

        let heard = audio::listen(audio::Vad::default, |samples| {
            if stop.load(Ordering::Relaxed) {
                return false;
            }
            // The name may have been switched off, or changed, while the
            // microphone was open. Noticing costs one `stat` per utterance.
            let now = wake::changed_at();
            if now != watching {
                watching = now;
                if !wake::load().enabled {
                    return false;
                }
            }

            room(&app, samples);
            true
        });

        if let Err(error) = heard {
            eprintln!("the wake loop stopped listening: {error}");
            std::thread::sleep(RETRY_AFTER);
        }
    }

    let _ = app.emit("wake.listening", false);
    show_listening(&app, false);
}

/// One burst of room speech, offered to the core.
fn room(app: &AppHandle, samples: Vec<i16>) {
    let Ok(wav) = audio::to_wav(&samples) else {
        return;
    };

    let locale = app
        .state::<Session>()
        .locale
        .lock()
        .ok()
        .and_then(|slot| slot.clone());

    let Ok(mut client) = Client::connect_as(&socket(), true) else {
        return;
    };

    let mut ask = |question: &serde_json::Value| -> Answer {
        // A question raised by something nobody asked for is answered by
        // nobody: the panel is not open, and silence is not consent.
        let assurance = question["assurance"].as_str().unwrap_or("ack");
        match requirement(assurance) {
            Some(needed) => Answer::once(verified(question, needed)),
            None => Answer::once(false),
        }
    };

    let Ok(turn) = client.submit_room(&wav, locale.as_deref(), &mut ask) else {
        return;
    };

    let outcome = turn
        .response
        .payload
        .get("outcome")
        .and_then(|it| it.as_str());
    match outcome {
        // Not the name. Nothing happened, and nothing is said about it.
        Some("ignored") | None => {}
        Some("woken") => {
            // The name, and nothing after it. Somebody is about to speak, so
            // the next utterance is a request rather than a room.
            let _ = app.emit("wake.woken", ());
            if let Some(window) = app.get_webview_window("panel") {
                reveal(&window);
            }
            follow(app);
        }
        Some(_) => {
            let result = TurnResult {
                heard: turn.heard,
                spoken: turn.speech.iter().map(|s| s.text.clone()).collect(),
                ok: turn.response.ok,
                outcome: "ran".into(),
                error: turn.response.error.as_ref().map(|e| e.message.clone()),
                data: turn.response.payload.get("data").cloned(),
            };
            speak(&result.spoken, locale.as_deref());
            let _ = app.emit("turn.completed", result);
        }
    }
}

/// The utterance after the name, taken as an ordinary turn.
fn follow(app: &AppHandle) {
    let _ = app.emit("turn.started", ());
    let outcome = audio::record_until_silence(audio::Vad::default())
        .map_err(|error| error.to_string())
        .and_then(|samples| audio::to_wav(&samples).map_err(|error| error.to_string()))
        .and_then(|wav| run_turn(app, Input::Recorded(wav), None));

    let _ = match outcome {
        Ok(result) => app.emit("turn.completed", result),
        Err(error) => app.emit(
            "turn.completed",
            TurnResult {
                heard: None,
                spoken: Vec::new(),
                ok: false,
                outcome: "failed".into(),
                error: Some(error),
                data: None,
            },
        ),
    };
}

/// The menu bar mark, filled while the microphone is open.
fn show_listening(app: &AppHandle, live: bool) {
    let bytes = if live { TRAY_LIVE } else { TRAY_ICON };
    if let (Some(tray), Ok(icon)) = (app.tray_by_id(TRAY), tauri::image::Image::from_bytes(bytes)) {
        let _ = tray.set_icon(Some(icon));
        let _ = tray.set_icon_as_template(true);
    }
}

/// What E.V. answers to, and whether it is listening for it.
#[tauri::command]
fn wake_state() -> wake::Wake {
    wake::load()
}

/// Change it. The loop is watching the file, so this is the whole switch:
/// nothing is signalled, nothing is restarted, and `ev --wake on` in a
/// terminal does exactly the same thing.
#[tauri::command]
fn set_wake(word: String, enabled: bool) -> Result<wake::Wake, String> {
    wake::save(&word, enabled)
}

/// Say what macOS answered, on its own connection.
///
/// Errors are dropped on purpose: a report is a courtesy to the core, and a
/// daemon that is not listening must not cost the person a turn or a prompt.
fn report(permission: &str, state: &str) {
    if let Ok(mut client) = Client::connect(&socket()) {
        let _ = client.report_permission(permission, state);
    }
}

/// The menu bar mark, drawn by `icons/generate.py` and carried in the binary.
const TRAY_ICON: &[u8] = include_bytes!("../icons/tray@2x.png");

/// The same mark with its middle filled, on screen for exactly as long as the
/// microphone is open. macOS shows its own indicator; its own indicator does
/// not say which application is listening (invariant 8).
const TRAY_LIVE: &[u8] = include_bytes!("../icons/tray-live@2x.png");

/// How long the loop waits before trying a microphone that would not open.
/// Long enough not to spin, short enough that plugging one in works without
/// restarting anything.
const RETRY_AFTER: Duration = Duration::from_secs(5);

/// How long a question waits for the person to answer it. Long, because they
/// are being asked something; not forever, because a panel that was closed
/// mid-question must not park a turn until the app quits.
const ANSWER_WITHIN: Duration = Duration::from_secs(120);

/// The longest a hold can last. A key that sticks, an app that steals the
/// key-up, a laptop that sleeps mid-sentence: any of them would otherwise
/// leave the microphone open until the app quits.
const LONGEST_HOLD: Duration = Duration::from_secs(30);

/// Shorter than this and it was a tap, not a sentence.
///
/// The panel still opens -- that is what a tap means -- but nothing is sent.
/// whisper on a fifth of a second of room noise returns whatever it
/// hallucinates from it, confidently.
const SHORTEST_HOLD: Duration = Duration::from_millis(250);

/// Where the daemon listens. The same path the CLI uses, because there is one
/// daemon and it is not ours to move.
fn socket() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home)
        .join("Library/Application Support/EV")
        .join("ev.sock")
}

#[derive(Default)]
struct Session {
    locale: Mutex<Option<String>>,
    /// Where an answer goes when the panel gives one. Present only while a
    /// turn is parked on a question; the app decides nothing itself.
    answering: Mutex<Option<Sender<Answer>>>,
    /// Where the key-up goes. Present only while a hold is recording, which
    /// is also how a key repeat is told from a second press.
    holding: Mutex<Option<Sender<()>>>,
    /// Raised when the app is quitting, so the wake loop puts the microphone
    /// down rather than being killed holding it.
    stop_listening: Arc<AtomicBool>,
}

#[derive(Clone, Serialize)]
struct TurnResult {
    heard: Option<String>,
    spoken: Vec<String>,
    ok: bool,
    outcome: String,
    error: Option<String>,
    /// Whatever the tool returned. The daemon's payload already carries it --
    /// `music.now_playing` answers the track and its cover here -- and the
    /// browser shell already passes it through, so until this field existed
    /// the same widget filled in one shell and stayed empty in the other.
    data: Option<serde_json::Value>,
}

/// Which macOS voice says it.
///
/// The setting wins when it names one, because voice quality on macOS is a
/// download: the compact voice ships with the system, the Enhanced and
/// Premium ones are fetched in Spoken Content, and the better one is not
/// always named as the one it replaces. Otherwise the locale chooses --
/// without naming her, macOS reads a Portuguese sentence with whatever the
/// system default is, which is usually Brazilian or English.
fn voice_for(saved: &settings::Settings, locale: Option<&str>) -> Option<String> {
    if let Some(named) = &saved.voice {
        return Some(named.clone());
    }
    match locale {
        Some("pt-PT") => Some("Joana".to_string()),
        _ => None,
    }
}

/// Say the answer out loud.
///
/// The app had no voice at all: it collected the spoken lines, handed them to
/// the window and stopped, so E.V. answered in writing in the one surface
/// built to be spoken to. `ev-host` has always said them in a terminal; this
/// is the same act in the app, where it belongs -- the audio device is the
/// signed process's, and that is this one.
///
/// On its own thread, because `say` returns when the sentence has finished
/// being said. Waiting for it would hold the turn open and the window would
/// show the answer only after it had been heard.
fn speak(lines: &[String], locale: Option<&str>) {
    let saved = settings::load();
    if !saved.speak || lines.is_empty() {
        return;
    }

    let said = lines.join(" ");
    let voice = voice_for(&saved, locale);

    std::thread::spawn(move || {
        let mut command = std::process::Command::new("say");
        if let Some(name) = voice {
            command.arg("-v").arg(name);
        }
        // "--" ends option parsing: a sentence starting with "-" is a
        // sentence, not a flag. The words are the model's, so they are never
        // trusted to be flag-shaped.
        command.arg("--").arg(said);

        if let Err(error) = command.status() {
            // Failing to speak is not a reason to fail a turn that already
            // happened. The words are on screen either way.
            eprintln!("could not speak: {error}");
        }
    });
}

/// What starts a turn.
enum Input {
    /// Typed in the panel.
    Text(String),
    /// Record until the room goes quiet. What the Speak button does.
    Listen,
    /// Already recorded, because a key was held down for it.
    Recorded(Vec<u8>),
    /// One frame, and what was said while looking at it.
    Seen(Vec<u8>, Option<String>),
}

fn run_turn(app: &AppHandle, input: Input, locale: Option<String>) -> Result<TurnResult, String> {
    // `true`: this is the signed app, and it can put macOS's own
    // authentication on screen. The daemon needs to know before it decides
    // whether a question can be asked here at all.
    let mut client = Client::connect_as(&socket(), true).map_err(|error| error.to_string())?;

    // The question goes to the panel and this thread waits for the answer.
    // The app decides nothing: no answer within the window is a decline, the
    // same rule the socket has for a closed connection and the terminal has
    // for a pipe.
    let mut ask = |question: &serde_json::Value| -> Answer {
        // Some questions are not the window's to answer. `verify` means macOS
        // has to establish who is at the machine, and a button in a window
        // E.V. drew cannot do that -- so the system is asked instead, and the
        // panel never sees the question at all.
        let assurance = question["assurance"].as_str().unwrap_or("ack");
        if let Some(requirement) = requirement(assurance) {
            return Answer::once(verified(question, requirement));
        }

        let (sender, receiver) = mpsc::channel();
        {
            let session = app.state::<Session>();
            let Ok(mut slot) = session.answering.lock() else {
                return Answer::once(false);
            };
            *slot = Some(sender);
        }

        if app.emit("confirmation.required", question.clone()).is_err() {
            return Answer::once(false);
        }

        let answered = receiver
            .recv_timeout(ANSWER_WITHIN)
            .unwrap_or_else(|_| Answer::once(false));

        if let Ok(mut slot) = app.state::<Session>().answering.lock() {
            *slot = None;
        }
        answered
    };

    let turn = match input {
        Input::Text(text) => client
            .submit(&text, locale.as_deref(), &mut ask)
            .map_err(|error| error.to_string())?,
        Input::Listen => {
            let samples = audio::record_until_silence(audio::Vad::default())
                .map_err(|error| error.to_string())?;
            let wav = audio::to_wav(&samples).map_err(|error| error.to_string())?;
            let _ = client.report_permission("microphone", "granted");
            client
                .submit_audio(&wav, locale.as_deref(), &mut ask)
                .map_err(|error| error.to_string())?
        }
        Input::Recorded(wav) => {
            // Bytes exist, so the microphone opened. That is the whole of what
            // macOS ever tells anyone about it.
            let _ = client.report_permission("microphone", "granted");
            client
                .submit_audio(&wav, locale.as_deref(), &mut ask)
                .map_err(|error| error.to_string())?
        }
        Input::Seen(frame, text) => client
            .submit_vision(&frame, text.as_deref(), locale.as_deref(), &mut ask)
            .map_err(|error| error.to_string())?,
    };

    let payload = &turn.response.payload;
    let result = TurnResult {
        heard: turn.heard,
        spoken: turn.speech.iter().map(|s| s.text.clone()).collect(),
        ok: turn.response.ok,
        outcome: payload
            .get("outcome")
            .and_then(|value| value.as_str())
            .unwrap_or("ran")
            .to_string(),
        error: turn.response.error.as_ref().map(|e| e.message.clone()),
        data: payload.get("data").cloned(),
    };
    speak(&result.spoken, locale.as_deref());
    Ok(result)
}

#[tauri::command]
async fn submit(
    app: AppHandle,
    text: String,
    session: State<'_, Session>,
) -> Result<TurnResult, String> {
    let locale = session.locale.lock().ok().and_then(|slot| slot.clone());
    tauri::async_runtime::spawn_blocking(move || run_turn(&app, Input::Text(text), locale))
        .await
        .map_err(|error| error.to_string())?
}

/// What the person clicked. Nothing else may call this into being: the sender
/// exists only while a turn is actually waiting.
///
/// `remember` is "always" (`open`) or "never" (`blocked`), and the daemon
/// applies it to the application *it* asked about -- the window cannot name a
/// different one.
#[tauri::command]
fn confirm(
    granted: bool,
    remember: Option<String>,
    session: State<'_, Session>,
) -> Result<(), String> {
    let sender = session
        .answering
        .lock()
        .map_err(|_| "the session is poisoned".to_string())?
        .take();

    match sender {
        Some(sender) => sender
            .send(Answer { granted, remember })
            .map_err(|_| "nobody is waiting".into()),
        None => Err("nothing is waiting on an answer".into()),
    }
}

/// Which strength a question asked for, if it asked for one at all.
fn requirement(assurance: &str) -> Option<ev_auth::Requirement> {
    match assurance {
        "owner" => Some(ev_auth::Requirement::Owner),
        "owner_and_password" => Some(ev_auth::Requirement::OwnerAndPassword),
        _ => None,
    }
}

/// Put the question to macOS.
///
/// The reason is what the person reads in the system's own dialog, so it says
/// what is about to happen rather than what the policy called it.
fn verified(question: &serde_json::Value, requirement: ev_auth::Requirement) -> bool {
    let tool = question["tool"].as_str().unwrap_or("act");
    let reason = match question["application"].as_str() {
        Some(application) => format!("let E.V. use {application} ({tool})"),
        None => format!("let E.V. run {tool}"),
    };

    match ev_auth::verify(&reason, requirement) {
        Ok(()) => true,
        Err(error) => {
            // A refusal and a Mac that cannot ask look the same from here, and
            // both mean the same thing: it does not run.
            eprintln!("not verified: {error}");
            false
        }
    }
}

#[tauri::command]
async fn listen(app: AppHandle, session: State<'_, Session>) -> Result<TurnResult, String> {
    let locale = session.locale.lock().ok().and_then(|slot| slot.clone());
    // Blocking: recording waits for a room to go quiet, and holding the async
    // runtime hostage for that would freeze the window it is drawing.
    tauri::async_runtime::spawn_blocking(move || run_turn(&app, Input::Listen, locale))
        .await
        .map_err(|error| error.to_string())?
}

/// Take one frame and ask about it.
///
/// The camera is opened, read and closed inside `take_frame`, and the panel is
/// told when it starts and when it stops. `CLAUDE.md` invariant 8 asks for a
/// visible active state: macOS shows its own indicator, and E.V. shows one
/// too, because a light that belongs to the system does not say which
/// application turned it on.
#[tauri::command]
async fn look(
    app: AppHandle,
    text: Option<String>,
    session: State<'_, Session>,
) -> Result<TurnResult, String> {
    let locale = session.locale.lock().ok().and_then(|slot| slot.clone());

    tauri::async_runtime::spawn_blocking(move || {
        let _ = app.emit("camera.started", ());
        let frame = camera::take_frame(camera::SESSION).map_err(|error| error.to_string());
        report(
            "camera",
            match &frame {
                Ok(_) => "granted",
                // A frame that did not arrive is not a refusal: the camera may
                // be in use, asleep, or absent. Only a refusal is a refusal.
                Err(why) if why.contains("refused") => "denied",
                Err(_) => "undetermined",
            },
        );
        // Emitted before the turn, not after it: the camera is already off,
        // and an indicator that stays on while a model thinks is a lie about
        // what the hardware is doing.
        let _ = app.emit("camera.stopped", ());

        run_turn(&app, Input::Seen(frame?, text), locale)
    })
    .await
    .map_err(|error| error.to_string())?
}

/// The map's ground: one file, beside the journal.
///
/// Never in the repository -- it is data and it is large, and `CLAUDE.md` says
/// where data lives. One archive rather than a directory of tiles, because
/// PMTiles is addressed by byte range, which is the whole reason a map can be
/// drawn here without a tile server anywhere in the picture.
fn basemap() -> PathBuf {
    settings::state_dir().join("maps").join("basemap.pmtiles")
}

/// Whether there is any ground to draw.
#[tauri::command]
fn map_present() -> bool {
    basemap().is_file()
}

/// One range of it, as bytes.
///
/// The renderer asks for the few kilobytes under the view and this hands them
/// over; no tile host is told anything, because there is no tile host. Bytes
/// rather than a number array: a range is tens of kilobytes, and JSON would
/// spell every one of them as three or four characters.
#[tauri::command]
fn map_range(offset: u64, length: u64) -> Result<tauri::ipc::Response, String> {
    use std::io::{Read, Seek, SeekFrom};

    // A ceiling, because the length arrives from the other side of the
    // window: a renderer asks for what it needs, and a bug there should not
    // become an allocation the size of the file here.
    const MOST: u64 = 32 * 1024 * 1024;

    let mut file = std::fs::File::open(basemap()).map_err(|error| error.to_string())?;
    file.seek(SeekFrom::Start(offset))
        .map_err(|error| error.to_string())?;

    let mut bytes = Vec::new();
    file.take(length.min(MOST))
        .read_to_end(&mut bytes)
        .map_err(|error| error.to_string())?;

    Ok(tauri::ipc::Response::new(bytes))
}

#[tauri::command]
async fn history(limit: u32, query: Option<String>) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut client = Client::connect(&socket()).map_err(|error| error.to_string())?;
        client
            .history(limit, query)
            .map_err(|error: ev_host::client::Error| error.to_string())
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
fn set_locale(locale: Option<String>, session: State<'_, Session>) {
    if let Ok(mut slot) = session.locale.lock() {
        *slot = locale.clone();
    }
    let mut saved = settings::load();
    saved.locale = locale;
    let _ = settings::save(&saved);
}

#[tauri::command]
fn settings() -> settings::Settings {
    settings::load()
}

/// Change the key that summons E.V.
///
/// The new one is registered before the old one is forgotten and the file is
/// written only if that worked: a shortcut another application already owns
/// must leave the working one in place rather than leaving E.V. with none.
#[tauri::command]
fn set_shortcut(app: AppHandle, shortcut: String) -> Result<(), String> {
    let mut saved = settings::load();
    if saved.shortcut == shortcut {
        return Ok(());
    }

    bind(&app, &shortcut).map_err(|error| format!("{shortcut} is not available: {error}"))?;
    let _ = app.global_shortcut().unregister(saved.shortcut.as_str());

    saved.shortcut = shortcut;
    settings::save(&saved)
}

/// Record while the key is held, then take the turn and push the result to the
/// panel.
///
/// The panel is not asking for this and cannot await it, so the result travels
/// as an event. A hotkey turn is otherwise identical to a typed one: the same
/// socket, the same lock in the core, the same confirmation.
fn hold(app: &AppHandle) {
    let (release, released) = mpsc::channel::<()>();
    {
        let session = app.state::<Session>();
        let Ok(mut slot) = session.holding.lock() else {
            return;
        };
        if slot.is_some() {
            // A key held down repeats. The first press is the one recording.
            return;
        }
        *slot = Some(release);
    }

    if let Some(window) = app.get_webview_window("panel") {
        reveal(&window);
    }
    let _ = app.emit("turn.started", ());

    let handle = app.clone();
    std::thread::spawn(move || {
        let started = std::time::Instant::now();
        let recorded = audio::record(|| {
            let _ = released.recv_timeout(LONGEST_HOLD);
        });

        if let Ok(mut slot) = handle.state::<Session>().holding.lock() {
            *slot = None;
        }

        if started.elapsed() < SHORTEST_HOLD {
            // A tap. The panel is open, which is what a tap asks for.
            let _ = handle.emit("turn.cancelled", ());
            return;
        }

        let locale = handle
            .state::<Session>()
            .locale
            .lock()
            .ok()
            .and_then(|slot| slot.clone());

        let outcome = recorded
            .map_err(|error| error.to_string())
            .and_then(|samples| audio::to_wav(&samples).map_err(|error| error.to_string()))
            .and_then(|wav| run_turn(&handle, Input::Recorded(wav), locale));

        let _ = match outcome {
            Ok(result) => handle.emit("turn.completed", result),
            Err(error) => handle.emit(
                "turn.completed",
                TurnResult {
                    heard: None,
                    spoken: Vec::new(),
                    ok: false,
                    outcome: "failed".into(),
                    error: Some(error),
                    data: None,
                },
            ),
        };
    });
}

/// Bind one key combination: down starts recording, up ends it.
///
/// Carbon's `RegisterEventHotKey` under this, not an event tap -- so E.V.
/// hears one combination and nothing else, and does not have to ask for
/// Accessibility to be listened to at all.
fn bind(app: &AppHandle, shortcut: &str) -> Result<(), String> {
    app.global_shortcut()
        .on_shortcut(shortcut, |app, _shortcut, event| match event.state {
            ShortcutState::Pressed => hold(app),
            ShortcutState::Released => {
                if let Ok(mut slot) = app.state::<Session>().holding.lock() {
                    if let Some(release) = slot.take() {
                        let _ = release.send(());
                    }
                }
            }
        })
        .map_err(|error| error.to_string())
}

/// Show the panel and give it the keyboard. Hidden rather than closed, because
/// a panel that is rebuilt on every summon loses whatever was on it.
fn reveal(window: &WebviewWindow) {
    let _ = window.show();
    let _ = window.set_focus();
}

/// Put the machine's own translucency behind the panel.
///
/// A floating window over whatever you were doing is what macOS uses this
/// material for, and E.V. is not the application to invent its own. Failing is
/// not fatal: a solid panel is a worse panel, not a broken one.
fn frost(window: &WebviewWindow) {
    if let Err(error) = window_vibrancy::apply_vibrancy(
        window,
        window_vibrancy::NSVisualEffectMaterial::HudWindow,
        None,
        Some(PANEL_RADIUS),
    ) {
        eprintln!("no vibrancy behind the panel: {error}");
    }
}

/// The three things a macOS window can do to itself.
///
/// Drawn by E.V. rather than by the system: the window has no title bar to
/// hang traffic lights from, and a title bar is the one piece of chrome a
/// head-up display cannot wear. Closing hides -- E.V. lives in the menu bar,
/// and the close button is not a quit button.
#[tauri::command]
fn window_control(window: WebviewWindow, action: String) -> Result<(), String> {
    match action.as_str() {
        "minimise" => window.minimize().map_err(|error| error.to_string()),
        "fullscreen" => {
            let full = window.is_fullscreen().map_err(|error| error.to_string())?;
            // Always-on-top and fullscreen together put the panel over the
            // menu bar of every other space. It goes back on the way out.
            let _ = window.set_always_on_top(full);
            window
                .set_fullscreen(!full)
                .map_err(|error| error.to_string())
        }
        "close" => window.hide().map_err(|error| error.to_string()),
        other => Err(format!("no such window action: {other}")),
    }
}

/// Put the panel away.
///
/// Escape, and losing focus. Hiding is not answering: a turn waiting on a
/// confirmation stays waiting, and the panel comes back with the question
/// still on it.
#[tauri::command]
fn dismiss(window: WebviewWindow) {
    let _ = window.hide();
}

pub fn run() {
    let saved = settings::load();

    // Before the window, before the tray: everything the app does is a
    // conversation with the core, and the core is now the app's own child --
    // which is what makes macOS attribute its Apple Events to E.V. rather
    // than to whatever terminal used to start it (ADR 0031).
    let core = Arc::new(Mutex::new(daemon::ensure(&socket())));
    eprintln!(
        "{}",
        core.lock().map(|it| it.describe()).unwrap_or_default()
    );

    let ending = core.clone();
    let session = Session::default();
    let quiet = session.stop_listening.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(Session {
            locale: Mutex::new(saved.locale.clone()),
            ..session
        })
        .invoke_handler(tauri::generate_handler![
            submit,
            listen,
            confirm,
            dismiss,
            window_control,
            look,
            history,
            map_present,
            map_range,
            set_locale,
            set_shortcut,
            settings,
            wake_state,
            set_wake
        ])
        .setup(move |app| {
            if let Some(panel) = app.get_webview_window("panel") {
                frost(&panel);
            }

            let show = MenuItem::with_id(app, "show", "Open E.V.", true, None::<&str>)?;
            // A core that could not start -- a permission not yet granted, a
            // daemon killed by hand -- should not need the app relaunched.
            let core_item = MenuItem::with_id(app, "core", "Start the core", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &core_item, &quit])?;

            // A menu bar item and no Dock icon: E.V. is somewhere to speak to,
            // not an application to switch to. LSUIElement in the plist is the
            // other half of that.
            let restarting = core.clone();
            TrayIconBuilder::with_id(TRAY)
                .icon(tauri::image::Image::from_bytes(TRAY_ICON)?)
                // A template is black with an alpha channel and macOS inverts
                // it for a dark menu bar. The app icon glows, which is right
                // in the Dock and wrong at 22 points next to the clock.
                .icon_as_template(true)
                .menu(&menu)
                .tooltip(format!(
                    "E.V.\n{}",
                    core.lock().map(|it| it.describe()).unwrap_or_default()
                ))
                .on_menu_event(move |app: &AppHandle, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("panel") {
                            reveal(&window);
                        }
                    }
                    "core" => {
                        if let Ok(mut state) = restarting.lock() {
                            daemon::stop(&mut state);
                            *state = daemon::ensure(&socket());
                            let said = state.describe();
                            eprintln!("{said}");
                            if let Some(tray) = app.tray_by_id(TRAY) {
                                let _ = tray.set_tooltip(Some(format!("E.V.\n{said}")));
                            }
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            // A shortcut another application already owns is a message, not a
            // reason to refuse to start: everything else about E.V. works
            // without it, and the panel is where the person can pick another.
            if let Err(error) = bind(app.handle(), &saved.shortcut) {
                eprintln!("the shortcut {} is not available: {error}", saved.shortcut);
            }

            // Asked for once, at startup, so the dialog arrives when the app
            // was opened rather than in the middle of a turn. Refusing is an
            // answer: everything except vision.look works without it.
            let handle = app.handle().clone();
            camera::request(move |granted| {
                let _ = handle.emit("camera.permission", granted);
                // Answered by the person, in a dialog only this process can
                // raise. The core has no other way to hear it.
                report("camera", if granted { "granted" } else { "denied" });
            });

            // The wake loop, if the name has been switched on. It watches the
            // file either way, so `ev --wake on` starts it without restarting
            // the app.
            let listening = app.handle().clone();
            let stop = app.state::<Session>().stop_listening.clone();
            std::thread::spawn(move || wake_loop(listening, stop));

            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the panel hides it. Quitting is a menu item, so the
            // window's close button does not end the session by accident.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }

            // Deliberately not hidden on losing focus any more. It was right
            // for a small panel summoned to type one line into; this is a
            // display with the trail, the settings and the state on it, and a
            // display that vanishes the moment you look at something else is
            // one you cannot read from. Escape puts it away, and so does the
            // menu bar.
        })
        .build(tauri::generate_context!())
        .expect("the app failed to start")
        .run(move |_app, event| {
            // What the app started, the app stops. An adopted daemon --
            // someone's terminal, watching it -- is left running.
            if matches!(event, tauri::RunEvent::Exit) {
                quiet.store(true, Ordering::Relaxed);
                if let Ok(mut state) = ending.lock() {
                    daemon::stop(&mut state);
                }
            }
        });
}
