# 0018 — Where speech happens

Status: accepted
Date: 2026-08-11

## Context

`CLAUDE.md` says three things about speech that cannot all be true at once:

1. "The signed native host owns TCC-facing capabilities: microphone, camera…"
2. Events, Python → native, include `transcription.partial`; and "the core
   depends on interfaces … `SpeechRecognizer` · `SpeechSynthesizer` ·
   `AudioSession`".
3. "Speech crosses this boundary as intent, not audio."

(1) puts the microphone in Rust. (2) puts transcription in Python, since a
partial transcript is pushed *from* the core and the recogniser interface lives
there. (3), read broadly, forbids the audio in (1) from ever reaching (2).

## Decision

**Capture is native; transcription is in the core.** The host opens the
microphone, because that is a TCC surface and TCC grants attach to a code
signature. The audio crosses the socket, and `whisper.cpp` runs in Python
behind `SpeechRecognizer`.

**"Intent, not audio" is read as being about the speaking direction** — its own
example is `speech.requested` — and not as a prohibition on the microphone
reaching the recogniser.

**Speaking is the host's job.** Python emits `speech.requested`; the host turns
it into sound. `SaySynthesizer` exists in the core for development and for the
CLI, where this process is the one in front of the user.

**The engine is never depended on.** `say(1)` now, `AVSpeechSynthesizer` in the
application, and nothing in the core changes when that happens.

**Carrying audio needs a protocol change**, so the version becomes 1.1 when
that lands.

## Alternatives rejected

**Transcribing in the host, so audio never crosses.** The cleanest reading of
(3), and it makes (2) meaningless: `SpeechRecognizer` in the core becomes a
decorative interface with no implementation, `transcription.partial` has to
become a command travelling the other way, and swapping whisper for anything
else becomes a Rust change. It was offered and declined.

**Naming no voice and letting macOS choose.** Measured: `say` reads a
Portuguese sentence with the system default, which is usually Brazilian or
English. `pt-PT` maps to Joana explicitly, on both sides.

**Speaking by default in the CLI.** A terminal that talks unbidden is a
surprise. `--speak` opts in; the host is what speaks in the application.

**Failing a turn when `say` fails.** The action already happened and the words
are on screen. Losing the audio is not a reason to report a failure that did
not occur.

## Consequences

**A gap became audible.** Tool responses are composed in English —
"Opening example.com" — so a `pt-PT` voice reads English words. `CLAUDE.md`
requires answering in the language of the request; doing that needs the locale
to reach the services, which needs session context that does not exist. It was
invisible while everything was printed; speaking made it obvious, which is an
argument for building the noisy end of a feature early.

`--locale` now exists on the CLI and is carried to the daemon as
`utterance.submit.locale`. It selects the voice and nothing else: it never
touches the utterance, because translating before routing mistranslates the
arguments.

Still to come in this phase: capture in the host, the audio command at protocol
1.1, `whisper.cpp` behind `SpeechRecognizer` with an explicit language hint,
and push-to-talk before VAD.
