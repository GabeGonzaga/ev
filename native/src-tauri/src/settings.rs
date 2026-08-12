//! What the app remembers between launches.
//!
//! Two things, and they are the two the person in front of it chooses: the
//! key that summons E.V., and the language it answers in.
//!
//! It lives beside the journal, in E.V.'s one directory, as JSON a person can
//! read and edit. It is deliberately not in the database: the database is the
//! core's, the app is a client of it, and a client that needs the daemon
//! running before it knows its own hotkey is a client that cannot be summoned
//! to start one.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

/// Hold this to talk. `Cmd+Shift+Space` rather than `Cmd+Space`, which is
/// Spotlight, and rather than a bare modifier, which needs an event tap and
/// with it the Accessibility permission -- a much larger thing to ask for
/// than a key combination.
pub const DEFAULT_SHORTCUT: &str = "CmdOrCtrl+Shift+Space";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub shortcut: String,
    pub locale: Option<String>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            shortcut: DEFAULT_SHORTCUT.to_string(),
            // None, not "en": the CLI's rule too. A session with no locale
            // set is not a Portuguese one, and guessing from what was said
            // would mean detecting the language before routing.
            locale: None,
        }
    }
}

pub fn state_dir() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home).join("Library/Application Support/EV")
}

pub fn path() -> PathBuf {
    state_dir().join("app.json")
}

/// The saved settings, or the defaults.
///
/// A file that will not parse is replaced by the defaults rather than
/// refusing to start: an app that cannot be opened cannot be used to fix its
/// own settings file.
pub fn load() -> Settings {
    std::fs::read_to_string(path())
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

pub fn save(settings: &Settings) -> Result<(), String> {
    let directory = state_dir();
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    let text = serde_json::to_string_pretty(settings).map_err(|error| error.to_string())?;
    std::fs::write(path(), text).map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_default_shortcut_is_not_spotlight() {
        assert_ne!(Settings::default().shortcut, "CmdOrCtrl+Space");
    }

    #[test]
    fn a_missing_field_falls_back_rather_than_failing() {
        // `serde(default)`: a settings file written by an older version, or
        // by a person editing it, still opens the app.
        let settings: Settings = serde_json::from_str("{}").expect("defaults");

        assert_eq!(settings.shortcut, DEFAULT_SHORTCUT);
        assert_eq!(settings.locale, None);
    }

    #[test]
    fn what_is_written_is_what_is_read() {
        let settings = Settings {
            shortcut: "Alt+Space".into(),
            locale: Some("pt-PT".into()),
        };

        let text = serde_json::to_string(&settings).expect("json");
        let read: Settings = serde_json::from_str(&text).expect("json");

        assert_eq!(read.shortcut, "Alt+Space");
        assert_eq!(read.locale.as_deref(), Some("pt-PT"));
    }
}
