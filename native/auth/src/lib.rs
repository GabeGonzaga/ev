//! Ask macOS to verify the owner.
//!
//! E.V. never sees a password and never draws a box to type one into. It asks
//! the system, the system asks the person, and what comes back is a yes or a
//! no. A program that renders its own password field is teaching people to
//! type their password into programs, which is the habit every credential
//! phish depends on.
//!
//! Two strengths, matching `Assurance` in `ev/domain/access.py`:
//!
//! * `Owner` — Touch ID or the login password, whichever the person has set
//!   up. `LAPolicy::DeviceOwnerAuthentication`.
//! * `OwnerAndPassword` — both, in one challenge. There is no policy for that,
//!   so it goes through a `SecAccessControl` built with `BiometryAny`,
//!   `DevicePasscode` and `And`, which is the documented way to require two
//!   factors at once.
//!
//! This is the only crate in the workspace that allows `unsafe`. It exists so
//! that the others can forbid it: everything Objective-C is behind one
//! function with one job.

use std::sync::mpsc;
use std::time::Duration;

use block2::RcBlock;
use objc2::runtime::Bool;
use objc2_core_foundation::CFRetained;
use objc2_foundation::{NSError, NSString};
use objc2_local_authentication::{LAAccessControlOperation, LAContext, LAPolicy};
use objc2_security::{
    kSecAttrAccessibleWhenUnlockedThisDeviceOnly, SecAccessControl, SecAccessControlCreateFlags,
};

/// How long to wait for an answer before giving up on the dialog.
///
/// Long, because someone may be looking for their finger or their password.
/// Not forever, because a turn that never ends holds the one lock every
/// surface shares.
const WITHIN: Duration = Duration::from_secs(120);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Requirement {
    /// Touch ID or the login password.
    Owner,
    /// Both, in one challenge.
    OwnerAndPassword,
}

#[derive(Debug)]
pub enum Error {
    /// The person said no, cancelled, or could not prove it was them. An
    /// answer, not a fault.
    Refused(String),
    /// This Mac cannot ask what was asked of it: no Touch ID, no password, or
    /// a combination it does not support.
    Unavailable(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Refused(why) => write!(formatter, "{why}"),
            Self::Unavailable(why) => write!(formatter, "this Mac cannot verify: {why}"),
        }
    }
}

impl std::error::Error for Error {}

/// Put the question to macOS and wait for the answer.
///
/// `reason` appears in the system's own dialog, so it says what is about to
/// happen in the words the person would use — "empty the Trash", not
/// "authorize a DESTRUCTIVE tool".
pub fn verify(reason: &str, requirement: Requirement) -> Result<(), Error> {
    let context = unsafe { LAContext::new() };
    let localized = NSString::from_str(reason);

    let (done, answer) = mpsc::channel::<Result<(), Error>>();
    let reply = RcBlock::new(move |granted: Bool, error: *mut NSError| {
        let outcome = if granted.as_bool() {
            Ok(())
        } else {
            Err(described(error))
        };
        // The receiver is gone only if the wait timed out, in which case
        // nobody is listening and there is nothing to be done about it.
        let _ = done.send(outcome);
    });

    match requirement {
        Requirement::Owner => unsafe {
            context.evaluatePolicy_localizedReason_reply(
                LAPolicy::DeviceOwnerAuthentication,
                &localized,
                &reply,
            );
        },
        Requirement::OwnerAndPassword => {
            let control = both()?;
            unsafe {
                context.evaluateAccessControl_operation_localizedReason_reply(
                    &control,
                    LAAccessControlOperation::UseItem,
                    &localized,
                    &reply,
                );
            }
        }
    }

    answer
        .recv_timeout(WITHIN)
        .unwrap_or_else(|_| Err(Error::Refused("nobody answered".into())))
}

fn described(error: *mut NSError) -> Error {
    if error.is_null() {
        return Error::Refused("refused".into());
    }
    Error::Refused(unsafe { (*error).localizedDescription() }.to_string())
}

/// An access control demanding biometry *and* the passcode.
///
/// Refused rather than downgraded when it cannot be built: a Mac that cannot
/// require both must say so, not quietly ask for one of them.
fn both() -> Result<CFRetained<SecAccessControl>, Error> {
    let flags = SecAccessControlCreateFlags::BiometryAny
        | SecAccessControlCreateFlags::DevicePasscode
        | SecAccessControlCreateFlags::And;

    unsafe {
        SecAccessControl::with_flags(
            None,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            flags,
            std::ptr::null_mut(),
        )
    }
    .ok_or_else(|| {
        Error::Unavailable("both Touch ID and a password cannot be required here".into())
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_two_strengths_are_distinct() {
        // They are not interchangeable, and a mapping that collapsed them
        // would silently ask for less than the level said.
        assert_ne!(Requirement::Owner, Requirement::OwnerAndPassword);
    }

    #[test]
    fn a_refusal_reads_as_an_answer_and_a_missing_factor_does_not() {
        assert_eq!(Error::Refused("cancelled".into()).to_string(), "cancelled");
        assert!(Error::Unavailable("no Touch ID".into())
            .to_string()
            .contains("cannot verify"));
    }

    #[test]
    fn both_factors_can_be_required_on_this_mac() {
        // Builds the access control without showing anything: it is the
        // policy object, not the prompt. If this fails, the strongest level
        // would refuse at the moment it is needed rather than at build time.
        assert!(both().is_ok());
    }
}
