//! The core, as a child of the app.
//!
//! `CLAUDE.md` says the Tauri host spawns the Python daemon as a sidecar and
//! owns its lifetime. Until now it did not, and the consequence was recorded
//! rather than fixed: the daemon spawns `osascript`, so macOS attributed every
//! Apple Event to whatever started the daemon -- a terminal. Spawning it here
//! puts the app at the top of that process tree, which is what TCC follows.
//!
//! Two rules shape the rest:
//!
//! * **A daemon that is already answering is left alone.** Someone running one
//!   in a terminal is doing it to watch it, and a second core on the same
//!   socket is not a thing that can work.
//! * **What the app started, the app stops** -- with SIGTERM, because the
//!   journal batches and the daemon flushes on that signal. SIGKILL would take
//!   the tail of the trail with it.

use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use ev_host::client::{Client, Error as ClientError};
use nix::sys::signal::{kill, Signal};
use nix::unistd::Pid;

/// How long to wait for a daemon that was just started to answer.
///
/// It opens a database, runs migrations and binds a socket. Ten seconds is
/// far more than that takes and short enough that a broken one is reported
/// rather than waited on.
const WITHIN: Duration = Duration::from_secs(10);

/// Where the tools the daemon spawns actually live.
///
/// A GUI application's children inherit `/usr/bin:/bin:/usr/sbin:/sbin` and
/// nothing else -- there is no shell in the chain to read a profile. `open`
/// and `osascript` are in `/usr/bin` and would be found; `whisper-cli` is
/// installed by Homebrew and would not, so a daemon started from the app
/// could route and act but never hear anything.
const ALSO_LOOK_IN: [&str; 2] = ["/opt/homebrew/bin", "/usr/local/bin"];

/// Where the daemon's own output goes.
///
/// Launched from Finder there is no terminal to inherit, so a daemon that
/// refuses something says it into nothing. This file is beside the journal,
/// and it is the first place to look when E.V. will not start.
const LOG: &str = "daemon.log";

/// How long a SIGTERM has to be enough. Past this the daemon is not flushing,
/// it is stuck, and the app is quitting either way.
const GOODBYE: Duration = Duration::from_secs(3);

pub enum State {
    /// The app started it, and will stop it.
    Started(Child),
    /// Someone else's, found already answering. Not ours to end.
    Adopted,
    /// Nothing is answering and nothing could be started.
    Absent(String),
}

impl State {
    pub fn describe(&self) -> String {
        match self {
            Self::Started(_) => "core: started by E.V.".into(),
            Self::Adopted => "core: already running".into(),
            Self::Absent(why) => format!("core: not running ({why})"),
        }
    }
}

/// The repository this app was built in.
///
/// A development answer, honestly named. A distributed E.V. would carry a
/// Python runtime inside the bundle, and bundling one is a decision nobody has
/// made yet (ADR 0031). Built here, the app knows where "here" is, and that is
/// exactly the case that exists today.
pub fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_default()
}

/// The interpreter that has E.V.'s dependencies, or nothing.
///
/// Only the project's own virtual environment. A GUI application inherits
/// almost no PATH, so a bare `python3` would find the system one -- which has
/// none of the dependencies and would fail several seconds later with an
/// import error instead of here with a sentence.
pub fn python(root: &Path) -> Option<PathBuf> {
    let candidate = root.join(".venv/bin/python");
    candidate.is_file().then_some(candidate)
}

/// The PATH to give the daemon: whatever this process has, plus the places a
/// package manager puts things. Appended rather than prepended, so a
/// deliberately chosen tool earlier in PATH stays the one that is found.
pub fn path_with_homebrew(inherited: Option<&str>) -> String {
    let mut parts: Vec<&str> = inherited
        .unwrap_or("/usr/bin:/bin:/usr/sbin:/sbin")
        .split(':')
        .filter(|part| !part.is_empty())
        .collect();

    for extra in ALSO_LOOK_IN {
        if !parts.contains(&extra) {
            parts.push(extra);
        }
    }

    parts.join(":")
}

/// Whether a daemon is already answering on this socket.
///
/// A handshake, not a file test: a socket file outlives the process that made
/// it, and `ev.sock` left behind by a crash is exactly the case that would
/// otherwise stop the app from starting a core.
pub fn answering(socket: &Path) -> Result<bool, String> {
    match Client::connect(socket) {
        Ok(_) => Ok(true),
        Err(ClientError::Unavailable(_)) => Ok(false),
        // It is there and it will not talk to us. Almost always a version
        // mismatch, and starting a second one would not fix it.
        Err(other) => Err(other.to_string()),
    }
}

/// Adopt a running daemon, or start one and wait for it to answer.
pub fn ensure(socket: &Path) -> State {
    match answering(socket) {
        Ok(true) => return State::Adopted,
        Ok(false) => {}
        Err(why) => return State::Absent(why),
    }

    let root = repository();
    let Some(interpreter) = python(&root) else {
        return State::Absent(format!("no interpreter at {}/.venv", root.display()));
    };

    // stderr is inherited on purpose: the daemon says why it refused things,
    // and launched from Finder that lands in the system log where Console.app
    // can be pointed at it.
    let mut command = Command::new(interpreter);
    command
        .args(["-m", "ev.cli", "--serve"])
        .current_dir(&root)
        .env(
            "PATH",
            path_with_homebrew(std::env::var("PATH").ok().as_deref()),
        );

    // Both streams to one file, if it can be opened. If it cannot, the daemon
    // still starts: a log is for diagnosing E.V., not a condition of running
    // it.
    let log = socket.parent().map(|directory| directory.join(LOG));
    if let Some(file) = log.as_ref().and_then(|path| {
        std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .ok()
    }) {
        if let Ok(second) = file.try_clone() {
            command.stdout(file).stderr(second);
        }
    }

    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(error) => return State::Absent(error.to_string()),
    };

    let deadline = Instant::now() + WITHIN;
    while Instant::now() < deadline {
        if matches!(answering(socket), Ok(true)) {
            return State::Started(child);
        }
        // It may have already given up, in which case waiting the full ten
        // seconds tells nobody anything.
        if matches!(child.try_wait(), Ok(Some(_))) {
            return State::Absent(said(log.as_deref()));
        }
        std::thread::sleep(Duration::from_millis(100));
    }

    // Started and not answering. Ending it is the point: an orphan holding a
    // socket nobody adopted is worse than no core at all, and the next launch
    // would find it and adopt something the app cannot manage.
    let mut orphan = State::Started(child);
    stop(&mut orphan);

    State::Absent(format!(
        "it did not answer within {}s. {}",
        WITHIN.as_secs(),
        said(log.as_deref())
    ))
}

/// The last thing the daemon said, for the message the app shows.
fn said(log: Option<&Path>) -> String {
    let Some(text) = log.and_then(|path| std::fs::read_to_string(path).ok()) else {
        return "It said nothing.".into();
    };

    match text.lines().rev().find(|line| !line.trim().is_empty()) {
        Some(last) => format!("Last line: {last}"),
        None => "It said nothing.".into(),
    }
}

/// End what the app started. Adopted daemons are left running.
pub fn stop(state: &mut State) {
    let State::Started(child) = state else {
        return;
    };

    // SIGTERM, not kill(): the journal batches, and the daemon flushes on this
    // signal. SIGKILL would take the last few turns with it.
    let pid = Pid::from_raw(child.id() as i32);
    if kill(pid, Signal::SIGTERM).is_err() {
        let _ = child.kill();
        return;
    }

    let deadline = Instant::now() + GOODBYE;
    while Instant::now() < deadline {
        match child.try_wait() {
            Ok(Some(_)) => return,
            Ok(None) => std::thread::sleep(Duration::from_millis(50)),
            Err(_) => break,
        }
    }

    // It had its chance to flush.
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_projects_own_interpreter_counts() {
        // A GUI app inherits almost no PATH, so "python3" would be the system
        // one: no dependencies, and a failure several seconds later instead of
        // a sentence now.
        let empty = std::env::temp_dir().join("ev-daemon-test-empty");
        std::fs::create_dir_all(&empty).expect("temp");

        assert_eq!(python(&empty), None);
    }

    #[test]
    fn the_repository_is_where_the_app_was_built() {
        // Not a guess about where E.V. is installed: the app was compiled in
        // the repository, so this is the one path it can know.
        assert!(repository().join("native/src-tauri/Cargo.toml").is_file());
    }

    #[test]
    fn a_stale_socket_file_is_not_a_daemon() {
        // `ev.sock` outlives a crash. A file test would see one and refuse to
        // start a core; a handshake sees nothing answering.
        let path = std::env::temp_dir().join("ev-daemon-test-not-a-socket");
        std::fs::write(&path, b"").expect("temp");

        assert_eq!(answering(&path), Ok(false));
    }

    #[test]
    fn the_daemon_can_find_whisper() {
        // The failure this prevents: launched from Finder, the app's children
        // get /usr/bin:/bin and nothing else, so `whisper-cli` -- Homebrew's,
        // and spawned by name -- is not found. E.V. would route and act and
        // never hear a word.
        let path = path_with_homebrew(Some("/usr/bin:/bin"));

        assert_eq!(path, "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin");
    }

    #[test]
    fn a_chosen_tool_stays_chosen() {
        // Appended, not prepended: someone with their own whisper earlier in
        // PATH meant it.
        let path = path_with_homebrew(Some("/opt/homebrew/bin:/usr/bin"));

        assert!(path.starts_with("/opt/homebrew/bin:/usr/bin"));
        assert_eq!(path.matches("/opt/homebrew/bin").count(), 1);
    }

    #[test]
    fn what_was_adopted_is_not_stopped() {
        let mut adopted = State::Adopted;
        stop(&mut adopted);

        assert!(matches!(adopted, State::Adopted));
    }
}
