# 0034 — The app asks macOS, and remembers the answer

**Status:** accepted
**Date:** 2026-08-13
**Phase:** 4.5

## Context

ADR 0033 gave every application a level and left two things unbuilt: `verify`
was satisfiable nowhere, and a level could only be set by editing a file or
typing `ev --app`. Both were deliberate — a level nothing can satisfy is
honest, and one that a click could satisfy is not — but neither is finished.

## Decision

**One crate speaks Objective-C, so the others do not have to.** `native/auth`
is the only crate in the workspace that allows `unsafe`; `ev-app` and `ev-host`
keep forbidding it outright. It exports one function, `verify(reason,
requirement)`, and everything about LocalAuthentication lives behind it.

**Two strengths, mapped to real APIs.**

- `owner` — Touch ID or the login password, whichever the person has set up:
  `LAPolicy::DeviceOwnerAuthentication`.
- `owner_and_password` — both, in one challenge. There is no policy for that,
  so it goes through a `SecAccessControl` built with `BiometryAny |
  DevicePasscode | And`, which is the documented way to require two factors at
  once. There is a test that builds it, so a Mac that cannot require both fails
  at `make app-check` rather than at the moment someone needs it. On this one,
  it can.

**E.V. never draws a password box.** It asks the system, the system asks the
person, and what comes back is a yes or a no. A program that renders its own
password field is teaching people to type their password into programs, which
is the habit every credential phish depends on. The reason string is what the
person reads — "let E.V. use Mail (mail.send)" — so it says what is about to
happen rather than what the policy called it.

**A question with an assurance above `ack` never reaches the panel.** The app
recognises it and puts it to macOS directly; the window is not offered a button
that would mean something weaker.

**A client says at the handshake whether it can verify.** `hello` carries
`verifies`, the signed app sends `true`, the terminal host and the CLI send
`false`, and the daemon refuses to ask a question a client cannot answer
properly. Claiming it falsely gains nothing: macOS does the asking, and a
client that cannot raise the dialog gets nothing to send back.

**An answer can set the level.** `confirmation.respond` carries `remember`:
`open` for "always", `blocked` for "never", absent for "just this once". The
panel offers all four.

**The application comes from the question, never from the answer.** The daemon
remembers which application it asked about and applies the level to that one.
Otherwise a client could answer a question about Photos by setting Mail to
`open`, which is the shape of every confused-deputy bug there is. There is a
test named after it.

## Alternatives rejected

**`security authorize`**, the command-line front end to Authorization Services.
No `unsafe`, no new crate, and it cannot tell "password" from "Touch ID" — the
distinction the levels are built on. Its dialog also describes a right, not
what E.V. is about to do.

**Two sequential prompts for the strongest tier** — biometrics, then owner
authentication. Simpler, and the second prompt is satisfied by Touch ID again,
so it requires one factor twice rather than two factors.

**Remembering a level after a plain yes.** A yes to one action is not a yes to
an application. "Always" is a separate button and says so.

**Letting the panel answer `verify` when the app cannot reach macOS.** That is
the downgrade the whole design exists to prevent. It refuses and says where the
level can be changed.
