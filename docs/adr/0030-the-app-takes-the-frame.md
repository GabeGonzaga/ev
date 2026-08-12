# 0030 — The app takes the frame

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 5

## Context

ADR 0029 put the frame's *arrival* beyond the model's reach and left one thing
unbuilt: the app could not take one. The browser could, and that was enough to
prove the path but not enough to be the product — `getUserMedia` asks in the
browser's name, and `CLAUDE.md` invariant 7 says the signed native host owns
TCC-facing capabilities.

## Decision

**`nokhwa`, with the `input-avfoundation` backend, as a macOS-only
dependency.** The host crate forbids `unsafe`, and talking to AVFoundation
directly means `objc2` and a great deal of it. The crate is declared under
`[target.'cfg(target_os = "macos")'.dependencies]` and the module behind
`#[cfg(target_os = "macos")]`, so the Linux build — which exists precisely to
prove the rest of the host is portable — does not grow a camera it has no
use for.

**One frame per call, and no handle to leave open.** `take_frame` opens the
device, warms it, reads, closes and returns bytes. There is no session object,
no `start`/`stop` pair and nothing for a bug elsewhere to leave running: a
session that cannot outlive the function that started it is the strongest form
of the timeout invariant 8 asks for.

Four frames are discarded first. A camera's first frames are black or
mid-exposure while the sensor wakes, and a black frame described confidently is
worse than a slow one.

**The deadline is real, and it is the part that is tested.** The capture runs on
its own thread and the caller gives up after ten seconds. Giving up is all that
happens — the thread is not killed, because a device read that has stopped
answering cannot be interrupted and a half-closed camera is worse than a slow
one. `bounded()` takes the work as a closure, so the failure it exists for — a
camera in use by another application, or a permission dialog nobody answered —
is a test with a sleeping closure rather than a hope.

**The indicator is E.V.'s own.** `camera.started` and `camera.stopped` are
emitted around the capture and the panel shows a red line while it is on.
macOS lights its own indicator, and that is the trustworthy one; it does not
say *which* application turned it on, which is what invariant 8 is asking for.
The stop event is emitted before the turn, not after: the camera is already
off by then, and an indicator that stays lit while a model thinks is a lie
about what the hardware is doing.

**Permission is asked for once, at startup.** The dialog arrives when the app
was opened rather than in the middle of a turn, and refusing it is an answer —
everything except `vision.look` works without it. `NSCameraUsageDescription`
and the `device.camera` entitlement are what make macOS ask at all rather than
refuse in a way that looks like a broken camera.

## Consequences

The dependency is not small: `nokhwa` pulls `image`, `mozjpeg` and the
CoreVideo bindings. It is confined to the macOS target and to one module behind
one function, which is the price of not writing `unsafe` AVFoundation by hand.

The frame is encoded as JPEG at quality 80 in the host, so what crosses the
socket is a few hundred KB rather than a few megabytes of RGB.

**Unproven on device, deliberately said so.** The bounded-deadline logic, the
protocol and the turn are tested; a real camera producing a real frame is not
something this machine can assert in a suite, and the app has not been run.

## Alternatives rejected

**A long-lived capture session, opened once and kept.** Faster after the first
frame, and it means a camera that is on when nobody is looking at it. The whole
of invariant 8 is about that not happening.

**Shelling out to a capture binary.** There is no camera equivalent of
`osascript` on macOS; every option is a third-party tool that would have to be
installed, signed and trusted. TCC would attribute the camera to it, not to
E.V., which is invariant 7 upside down.

**Letting the panel capture through the webview.** The webview is not the
signed host, and a permission the app holds should not be exercised by the
window it draws.
