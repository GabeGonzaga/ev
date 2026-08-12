//! The menu bar and the panel.
//!
//! This is the same conversation `ev-host` has, with a window around it: it
//! connects to the daemon over the same socket, speaks the same protocol, and
//! shares the client and the microphone code rather than owning copies.
//!
//! It lives in the app rather than in a helper because TCC attributes a
//! permission to the app (ADR 0019), and because a menu bar is a place to
//! show state that a terminal has nowhere to put.

use std::path::PathBuf;
use std::sync::mpsc::{self, Sender};
use std::sync::Mutex;
use std::time::Duration;

use ev_host::audio;
use ev_host::client::Client;
use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, State, WebviewWindow};

/// How long a question waits for the person to answer it. Long, because they
/// are being asked something; not forever, because a panel that was closed
/// mid-question must not park a turn until the app quits.
const ANSWER_WITHIN: Duration = Duration::from_secs(120);

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
    answering: Mutex<Option<Sender<bool>>>,
}

#[derive(Serialize)]
struct TurnResult {
    heard: Option<String>,
    spoken: Vec<String>,
    ok: bool,
    outcome: String,
    error: Option<String>,
}

fn run_turn(
    app: &AppHandle,
    text: Option<String>,
    listen: bool,
    locale: Option<String>,
) -> Result<TurnResult, String> {
    let mut client = Client::connect(&socket()).map_err(|error| error.to_string())?;

    // The question goes to the panel and this thread waits for the answer.
    // The app decides nothing: no answer within the window is a decline, the
    // same rule the socket has for a closed connection and the terminal has
    // for a pipe.
    let mut ask = |question: &serde_json::Value| -> bool {
        let (sender, receiver) = mpsc::channel();
        {
            let session = app.state::<Session>();
            let Ok(mut slot) = session.answering.lock() else {
                return false;
            };
            *slot = Some(sender);
        }

        if app.emit("confirmation.required", question.clone()).is_err() {
            return false;
        }

        let granted = receiver.recv_timeout(ANSWER_WITHIN).unwrap_or(false);

        if let Ok(mut slot) = app.state::<Session>().answering.lock() {
            *slot = None;
        }
        granted
    };

    let turn = if listen {
        let samples = audio::record_until_silence(audio::Vad::default())
            .map_err(|error| error.to_string())?;
        let wav = audio::to_wav(&samples).map_err(|error| error.to_string())?;
        client
            .submit_audio(&wav, locale.as_deref(), &mut ask)
            .map_err(|error| error.to_string())?
    } else {
        client
            .submit(&text.unwrap_or_default(), locale.as_deref(), &mut ask)
            .map_err(|error| error.to_string())?
    };

    let payload = &turn.response.payload;
    Ok(TurnResult {
        heard: turn.heard,
        spoken: turn.speech.iter().map(|s| s.text.clone()).collect(),
        ok: turn.response.ok,
        outcome: payload
            .get("outcome")
            .and_then(|value| value.as_str())
            .unwrap_or("ran")
            .to_string(),
        error: turn.response.error.as_ref().map(|e| e.message.clone()),
    })
}

#[tauri::command]
async fn submit(
    app: AppHandle,
    text: String,
    session: State<'_, Session>,
) -> Result<TurnResult, String> {
    let locale = session.locale.lock().ok().and_then(|slot| slot.clone());
    tauri::async_runtime::spawn_blocking(move || run_turn(&app, Some(text), false, locale))
        .await
        .map_err(|error| error.to_string())?
}

/// What the person clicked. Nothing else may call this into being: the sender
/// exists only while a turn is actually waiting.
#[tauri::command]
fn confirm(granted: bool, session: State<'_, Session>) -> Result<(), String> {
    let sender = session
        .answering
        .lock()
        .map_err(|_| "the session is poisoned".to_string())?
        .take();

    match sender {
        Some(sender) => sender.send(granted).map_err(|_| "nobody is waiting".into()),
        None => Err("nothing is waiting on an answer".into()),
    }
}

#[tauri::command]
async fn listen(app: AppHandle, session: State<'_, Session>) -> Result<TurnResult, String> {
    let locale = session.locale.lock().ok().and_then(|slot| slot.clone());
    // Blocking: recording waits for a room to go quiet, and holding the async
    // runtime hostage for that would freeze the window it is drawing.
    tauri::async_runtime::spawn_blocking(move || run_turn(&app, None, true, locale))
        .await
        .map_err(|error| error.to_string())?
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
        *slot = locale;
    }
}

/// Show the panel and give it the keyboard. Hidden rather than closed, because
/// a panel that is rebuilt on every summon loses whatever was on it.
fn reveal(window: &WebviewWindow) {
    let _ = window.show();
    let _ = window.set_focus();
}

pub fn run() {
    tauri::Builder::default()
        .manage(Session::default())
        .invoke_handler(tauri::generate_handler![
            submit, listen, confirm, history, set_locale
        ])
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Open E.V.", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;

            // A menu bar item and no Dock icon: E.V. is somewhere to speak to,
            // not an application to switch to. LSUIElement in the plist is the
            // other half of that.
            TrayIconBuilder::new()
                .icon(app.default_window_icon().cloned().ok_or("no icon")?)
                .menu(&menu)
                .tooltip("E.V.")
                .on_menu_event(|app: &AppHandle, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("panel") {
                            reveal(&window);
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the panel hides it. Quitting is a menu item, so the
            // window's close button does not end the session by accident.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("the app failed to start");
}
