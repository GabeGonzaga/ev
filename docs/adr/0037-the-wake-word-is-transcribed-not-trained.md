# 0037 — The wake word is transcribed, not trained

**Status:** accepted
**Date:** 2026-08-14
**Phase:** 6

## Context

Phase 6, and the requirement that shaped it: E.V. should answer to "E.V.", and
somebody else should be able to make it answer to something else.

That second half rules out the usual answer. A keyword spotter — openWakeWord,
Porcupine — recognises one sound it was trained on. Custom words mean training
a model per word, or a console, an account and a key. "Any word the user
types" and "a trained model per word" cannot both be true.

## Decision

**Transcribe the room and compare strings.** whisper already runs here, it
already knows the languages this is spoken in, and a name it has never seen is
no harder for it than one it has. Changing the wake word is editing a file.

**A second, smaller model.** `tiny` (78 MB) hears the name; `small` hears the
request. The wake pass runs on every burst of speech in the room rather than
once per request, and what it gets wrong is caught by a string comparison
rather than by the model. Measured: 0.3–0.4 s per burst against `small`'s
0.72 s.

**The name must start the utterance.** "I was telling Ana that E.V. can play
music" is somebody talking *about* E.V., and acting on it is the failure that
makes people switch a wake word off and never switch it back on.

**Fillers are not part of anyone's name.** "Hey E.V." and "E.V." are one
request, so `hey`, `ok`, `olá` and their relatives are stripped before
matching.

**Spellings are configurable, and the defaults are measured rather than
guessed.** Said into this machine's microphone, "E.V." comes back as `EV`, as
`Evie` when the sentence is Portuguese, and as `H-E-V` when "hey" runs into
it. All three are defaults. `heavy` — which "hey E.V." also becomes — is
deliberately absent: a name that is also an ordinary word wakes on "heavy rain
tomorrow", and the start-of-utterance rule does not save you from a word people
actually say.

Letter-by-letter spelling is generated only for names of three characters or
less. `E V` is how whisper writes it half the time; `j a r v i s` would only
ever match somebody spelling it out.

**Nothing that was not addressed to E.V. leaves a trace.** Room audio that did
not begin with the name produces no turn, no event, and no journal entry. The
recording is deleted with the same `finally` that deletes every other one.

**Off until asked for.** Always-on listening is a decision somebody makes, not
a default they discover, and `ev --wake on` says in plain words what it costs.

## What this costs, said plainly

While the loop runs, everything said near this machine is transcribed on it.
Nothing leaves, nothing is stored, and only what began with the name is acted
on — but the audio is read, which is more than a keyword spotter does. A
spotter matches a spectral pattern and never forms words at all.

That is the trade for a name anybody can change to anything, in any language,
without training a model. It is the right trade for a local-first assistant
and it is not a free one, which is why it is written here rather than implied.

## Two-letter names are hard

Measured, with `say` and `tiny`:

| Said | Written | Woke |
|---|---|---|
| "E.V." | `EV.` | yes |
| "E.V., play the album Blonde" | `EV play the album blonde.` | yes |
| "Hey E.V., pause" | `H-E-V, pause.` | yes, via `hev` |
| "E.V., toca o álbum Blonde" | `Evie, toca o álbum blonde.` | yes, via `evie` |
| "Jarvis, pause the music" | `Jarvis pulls the music.` | yes |
| "Computer, pause the music" | `computer pulls the music.` | yes |
| "every evening" | `Every evening.` | no |
| "heavy rain tomorrow" | `Heavy rain tomorrow.` | no |

A third of a second of speech carries little information, and two letters carry
less. Longer names work first time and need no variants at all. `ev` is the
default because it is E.V.'s name; anybody who finds it unreliable should give
it a longer one, and that is now a supported thing rather than a code change.

## Alternatives rejected

**openWakeWord.** Pre-trained for a handful of phrases; a custom word needs a
training run and a dataset. The requirement was that a user could change it.

**Porcupine.** Excellent, and custom words come from a web console with an
account and a key. Weights that arrive with a licence check are not what
"stays on this machine" means.

**`SFSpeechRecognizer` keyword spotting.** On-device availability varies by
language, and `CLAUDE.md` already puts it at "a fallback backend at most".

**Running `small` on room audio.** 0.72 s per burst of somebody else's
conversation, for a decision a 78 MB model makes in 0.3 s.
