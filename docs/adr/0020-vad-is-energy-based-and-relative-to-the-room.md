# 0020 — VAD is energy-based, and relative to the room

Status: accepted
Date: 2026-08-11

## Context

`CLAUDE.md` orders the audio work: push-to-talk first, VAD second, wake word
last. Push-to-talk works. VAD replaces the keypress that ends a recording with
a decision about when the speaker stopped.

## Decision

**Energy, not a model.** Root-mean-square per 50 ms frame, and speech is what
stands well above the room.

**The threshold is relative to the room, measured each time.** The first 300 ms
is spent listening to the room and the threshold is four times that floor. A
fixed number works in one kitchen and fails in the next.

**A pause is not an end.** 800 ms of silence ends an utterance; less does not.

**Silence is refused, not transcribed.** Five seconds with nothing said returns
"nothing was said" rather than an empty recording.

**A cap on length.** Twenty seconds, so a stuck microphone cannot record until
the disk fills.

**The decision is made outside the audio callback.** The callback runs on a
realtime thread; it collects samples and nothing else. The loop polls every
50 ms, which is nothing against a silence measured in hundreds.

**Push-to-talk stays.** `--listen` is the keypress, `--vad` is the room. The
keypress is the one that always works.

## Alternatives rejected

**Silero or another model-based VAD.** More accurate, particularly in noise,
and it is a model to download, a runtime to carry, and weights to hold resident
next to whisper and the router. `CLAUDE.md` is already unwilling to hold the
LLM and STT at once. This waits for a measurement showing energy is not enough.

**A fixed absolute threshold.** Simpler, and it fails the moment the room
changes. There is a small absolute floor underneath the relative one, for a
room quiet enough that four times its noise is still nothing.

**Deciding inside the audio callback.** Fewer moving parts, and the callback is
realtime: work there is measured in dropped frames.

**Trimming the leading silence before sending.** whisper handles it, and every
transformation applied to a recording before transcription is a chance to
remove the first syllable of what someone said.

## Consequences

**It will treat loud music or a nearby conversation as speech**, because by
this measure they are. That is the known limit of energy detection, stated
rather than discovered later. The keypress remains for those rooms.

**The decision logic is unit-tested; the microphone is not.** A `Vad` takes
levels and returns decisions, so a sentence with a pause in it, a fan that is
not speech, and a room where nothing happens are all testable without a room.
Faking the device would prove only that a fake returns what it was told to.

**Untested by anything here: a real voice.** The loop has never heard one --
capture was verified with an immediate stop and transcription with synthesised
speech. Whether 800 ms is the right pause, and whether four times the floor is
the right threshold, are questions for the first person who talks to it.
