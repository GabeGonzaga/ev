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

/// Hold this to talk, and to bring E.V. up.
///
/// `Shift+Space`, asked for by name and set against the advice below, which
/// is left here because the trade is real and the way out should be one edit.
///
/// It is global, so it is taken everywhere rather than only here, and the
/// pattern that triggers it -- Shift still down when the space bar goes down
/// -- is one ordinary typing produces all day: `OK ` and `E.V. ` both end
/// that way, because the thumb reaches the bar before the little finger has
/// let go. Every one of those opens E.V. and starts recording, in whatever
/// application was being typed into. In a browser it also takes `Shift+Space`
/// away from scrolling a page back up.
///
/// A letter is the shape that does not have this problem -- `Ctrl+Shift+E`
/// was the previous default and is a one-word change back. Space chords with
/// a second modifier are the middle ground: `Ctrl+Shift+Space` is free of the
/// system's own bindings, and Shift alone is not.
///
/// Note, since it comes up: `Space+Shift+E` is not an accelerator and cannot
/// be one. A shortcut is modifiers plus exactly one key, and the modifiers
/// are only Command, Control, Option and Shift. Space can be the key, or
/// nothing at all.
pub const DEFAULT_SHORTCUT: &str = "Shift+Space";

/// Defaults this app has shipped before.
///
/// A saved file carrying one of these was almost certainly never chosen: the
/// whole settings struct is written whenever anything in it changes, so
/// picking a language freezes whatever the shortcut default happened to be
/// that day, and every later default is then invisible to that install. A
/// value equal to a past default is therefore treated as unset. Anything else
/// is somebody's own choice and is left exactly alone.
const SUPERSEDED: &[&str] = &[
    "CmdOrCtrl+Shift+Space",
    "Alt+Shift+Space",
    "Ctrl+Shift+Space",
    "Ctrl+Shift+E",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub shortcut: String,
    pub locale: Option<String>,
    /// Which macOS voice says it, by the name `say -v '?'` prints.
    ///
    /// None lets the locale choose, which is what most people want. It exists
    /// because voice quality on macOS is a download: the compact voice ships
    /// with the system and the Enhanced and Premium ones are fetched in
    /// Spoken Content, and once fetched they may be named differently from
    /// the compact one they replace. Naming the voice here is how someone
    /// points E.V. at the better one without waiting for a release.
    pub voice: Option<String>,
    /// Whether E.V. says its answers out loud at all.
    ///
    /// On, because an assistant that only writes is a text box. Off is one
    /// edit away for a shared office or a late night, and the answer is still
    /// on screen either way.
    pub speak: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            shortcut: DEFAULT_SHORTCUT.to_string(),
            // None, not "en": the CLI's rule too. A session with no locale
            // set is not a Portuguese one, and guessing from what was said
            // would mean detecting the language before routing.
            locale: None,
            voice: None,
            speak: true,
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
    let mut settings: Settings = std::fs::read_to_string(path())
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default();

    if SUPERSEDED.contains(&settings.shortcut.as_str()) {
        settings.shortcut = DEFAULT_SHORTCUT.to_string();
    }

    settings
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
        // The two the voice needs: no voice named, and speaking on. A file
        // written before either existed still opens an app that talks.
        assert_eq!(settings.voice, None);
        assert!(settings.speak);
    }

    #[test]
    fn a_past_default_is_not_a_choice() {
        // The trap this closes: saving a language froze the shortcut, so the
        // install went on using a default that had since been replaced and
        // nothing short of hand-editing the file could move it.
        for stale in SUPERSEDED {
            assert_ne!(
                *stale, DEFAULT_SHORTCUT,
                "a superseded default must not be the current one",
            );
        }
    }

    #[test]
    fn what_is_written_is_what_is_read() {
        let settings = Settings {
            shortcut: "Alt+Space".into(),
            locale: Some("pt-PT".into()),
            voice: Some("Joana (Premium)".into()),
            speak: false,
        };

        let text = serde_json::to_string(&settings).expect("json");
        let read: Settings = serde_json::from_str(&text).expect("json");

        assert_eq!(read.shortcut, "Alt+Space");
        assert_eq!(read.locale.as_deref(), Some("pt-PT"));
        // A voice name with spaces and brackets in it is what Spoken Content
        // actually calls the downloaded voices, so it has to survive the trip.
        assert_eq!(read.voice.as_deref(), Some("Joana (Premium)"));
        assert!(!read.speak);
    }
}
