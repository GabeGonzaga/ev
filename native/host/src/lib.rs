//! What the host does, as a library.
//!
//! Two binaries need this: `ev-host`, which is a terminal client, and the
//! Tauri app, which is the same conversation with a window around it. Sharing
//! the code is the alternative to keeping two copies of a protocol client
//! honest by hand.

pub mod audio;
/// macOS only: on Linux there is no camera to open and no app to open it for.
#[cfg(target_os = "macos")]
pub mod camera;
pub mod client;

/// The generated view of the contract, produced from
/// `protocol/generated/ev.schema.json` and committed beside it.
/// `make protocol-check-rust` fails if the two disagree.
#[path = "../../../protocol/generated/rust/protocol.rs"]
#[allow(dead_code, clippy::derivable_impls, clippy::to_string_trait_impl)]
pub mod protocol;
