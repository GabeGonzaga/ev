# 0019 — Capture in the host, and what the microphone actually asked

Status: accepted
Date: 2026-08-11

## Context

ADR 0018 put capture in the signed host and transcription in the core. This is
the capture half: `cpal` over CoreAudio, push-to-talk, and audio leaving as
`audio.submit`.

## Decision

**The host converts before it sends.** 16 kHz, mono, 16-bit — what whisper
wants — rather than the device's 48 kHz stereo. A three-second utterance leaves
as ~96 KB instead of ~576 KB, and the core never has to know what a sample rate
is.

**Linear interpolation, not a resampling library.** Speech downsampled to
16 kHz has aliasing that no measurement here has shown whisper to care about.
`rubato` is a dependency to add when something measures a difference.

**Push-to-talk is a keypress.** Recording starts, and the keypress that ends it
is the release. A global hotkey needs an event tap and an Accessibility grant,
which is phase 3's problem, and `CLAUDE.md` puts push-to-talk before VAD and
VAD before a wake word.

**The transcript is printed even when it is right.** Being misheard should be
visible in the words rather than inferred from the wrong thing happening.

**Connect before recording.** No daemon means nothing to send audio to, and
recording someone regardless would be recording for no reason.

## What the microphone actually did

**Nothing asked.** Capture worked on the first run with no permission dialog at
all, because TCC attributes a request to the *responsible process* — here the
terminal that launched the binary, which already holds a microphone grant. The
signature is real and verified, but it is not yet the identity macOS is
deciding about.

This qualifies the reason given in ADR 0017 for signing early. Signing does not
give the host its own TCC identity while it is launched from a shell; it gets
one when it is a bundled `.app` with its own `Info.plist` and
`NSMicrophoneUsageDescription`, which is phase 3. What signing bought so far is
a stable identity that will not churn *when* that happens, which is worth
having and is less than was claimed.

## Alternatives rejected

**Shipping the device's native format and resampling in the core.** Six times
the bytes over the socket, and it would put an audio concern in the layer that
was explicitly kept free of them.

**AVFoundation through objc2 instead of `cpal`.** More macOS-idiomatic, several
more dependencies, and no capability this needs that `cpal` lacks. It becomes
the right answer when the host needs an audio *session* — ducking, route
changes, interruptions — which is the same moment `AudioSession` stops being a
name in `CLAUDE.md` and starts being a type.

**Recording for a fixed number of seconds.** Simpler, and wrong for a push to
talk: it either cuts people off or records silence.

## Consequences

A silent failure surfaced and was fixed: when the daemon refused a turn — as it
does for an empty recording, with "nothing was said" — the host printed the
exit code and swallowed the sentence. It prints the reason now.

`unsafe_code = "forbid"` still holds with audio in the crate: `cpal` owns the
unsafe, the host owns none.

The capture path has unit tests for the parts that are testable without a
microphone — downmixing, resampling, clipping, the WAV header. The device
itself is not faked: nothing would be learned from asserting that a fake
returns what it was told to.
