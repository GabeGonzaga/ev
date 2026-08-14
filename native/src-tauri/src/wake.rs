//! What E.V. answers to, as the app needs to know it.
//!
//! The core owns the decision -- it holds the model that hears the name and
//! the file that spells it. The app only needs one thing from that file:
//! whether to hold the microphone open. It reads it directly rather than
//! asking over the socket, for the same reason it reads `app.json` directly:
//! this is a settings file in E.V.'s one directory, and a window that cannot
//! know whether it is listening until a daemon answers is a window that
//! cannot show it.
//!
//! Re-read when it changes, so `ev --wake on` takes effect without restarting
//! anything.

use std::path::PathBuf;
use std::time::SystemTime;

use serde::{Deserialize, Serialize};

use crate::settings::state_dir;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(default)]
pub struct Wake {
    pub word: String,
    pub enabled: bool,
}

impl Default for Wake {
    fn default() -> Self {
        Self {
            word: "ev".to_string(),
            // Off unless the file says otherwise. Always-on listening is a
            // decision somebody makes, not a default they discover.
            enabled: false,
        }
    }
}

pub fn path() -> PathBuf {
    state_dir().join("wake.json")
}

pub fn load() -> Wake {
    std::fs::read_to_string(path())
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

/// Write it back, keeping every field the core wrote that the app does not
/// model -- `also`, above all. The app knows two of this file's keys, and a
/// window saving a settings file must not quietly drop what it never read.
pub fn save(word: &str, enabled: bool) -> Result<Wake, String> {
    let mut whole: serde_json::Value = std::fs::read_to_string(path())
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_else(|| serde_json::json!({}));

    let word = word.trim();
    if word.is_empty() {
        return Err("A name with nothing in it is not a name.".into());
    }

    whole["word"] = serde_json::Value::String(word.to_string());
    whole["enabled"] = serde_json::Value::Bool(enabled);

    let folder = path();
    let folder = folder.parent().ok_or("no state directory")?;
    std::fs::create_dir_all(folder).map_err(|error| error.to_string())?;
    std::fs::write(
        path(),
        serde_json::to_string_pretty(&whole).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;

    Ok(load())
}

/// When the file last changed, so a loop can notice without parsing it.
pub fn changed_at() -> Option<SystemTime> {
    std::fs::metadata(path())
        .and_then(|about| about.modified())
        .ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn listening_is_off_until_the_file_says_otherwise() {
        assert!(!Wake::default().enabled);
    }

    #[test]
    fn a_name_with_nothing_in_it_is_refused() {
        assert!(save("   ", true).is_err());
    }

    #[test]
    fn a_file_written_by_an_older_version_still_reads() {
        let wake: Wake = serde_json::from_str(r#"{"word":"jarvis"}"#).expect("json");

        assert_eq!(wake.word, "jarvis");
        assert!(!wake.enabled);
    }
}
