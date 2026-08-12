# 0029 — A frame arrives; it is never fetched

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 5

## Context

`CLAUDE.md` invariant 8: "Camera and microphone require explicit permission and
a visible active-state indicator. Neither may be started by ambiguous model
inference. Sessions have a timeout. Frames are not persisted by default."

The obvious shape for a camera tool violates the second sentence by
construction. `vision.look()` that opens the camera means a model deciding to
open a camera, and "ambiguous model inference" is exactly what a 0.62-confidence
routing is.

## Decision

**The frame is bound to the turn before the turn starts.** A surface captures
it because a person pressed something — the Look button, and later a key in the
app — and hands it over with `vision.submit`, the same shape `audio.submit` has
and for the same reason. `Frames` holds it for one turn and `clear()` runs in a
`finally`.

**`vision.look` has one argument and it is not an image.** There is no field
that names a file, a device, a camera or a frame; the only thing the model may
supply is the question. So the model can decide *to answer about what is here*,
and has no way to decide *to look*. When nothing bound a frame, the tool fails
with "the camera is not on" rather than a model describing a room it invented.

**The permission gate is real.** `vision.look` declares `Permission.CAMERA`, so
without it the policy denies before anything is shown to any model — a frame
that a refused tool still sent onward would be the whole point missed, and there
is a test that says so.

**No words means describe it; words mean an ordinary turn.** Pressing Look with
an empty box calls `vision.look` directly through `Registry.call()` — pressing
the button *is* the request, and inventing a sentence to route would be putting
words in someone's mouth. With words, it is a normal turn that happens to have
something to look at, and the router may or may not reach for the camera.

**Frames are not persisted, and here that is a property rather than a promise.**
Audio reaches disk because whisper reads a path; the daemon writes a temporary
file and deletes it in a `finally`. A vision model takes bytes in the request
body, so a frame exists in this process and in Ollama's, and then it does not.
It is not an argument, so the journal records the question and the answer and
has nothing of the image to write down.

**The vision model is a third role, loaded per capture.** `keep_alive: "0"` is
the latency budget's "load the vision model on capture, unload after" written
as configuration. It is `gemma3:12b` by default — above the 9B ceiling, which
`CLAUDE.md` allows for work that is not the voice brain — and it is excluded
from `models()`, because nothing about it is resident.

Measured on an M2 Pro: **14–19 s** from frame to answer, most of it loading
8 GB of weights that are then dropped. That is the price of not evicting the
router, whose reload costs 7.5 s on the next voice turn. A smaller vision model
is one line in `models.json`, which is what the role is for.

The pt-PT answers came back in European Portuguese, unprompted beyond the
"responde em português de Portugal" line the service adds.

## What is not built

**Capture in the app.** AVFoundation, an indicator that is visible while the
camera is on, and a session timeout are three decisions, and invariant 8 asks
for all of them. In the browser they already exist and are not E.V.'s: the page
uses `getUserMedia`, so the browser asks in its own name and shows its own
indicator, and the stream is stopped in a `finally` after a single frame — a
session short enough that a timeout has nothing to bound.

## Alternatives rejected

**A `camera.start` / `camera.stop` pair of tools.** Then the model owns the
camera's lifetime, which is the sentence in invariant 8 that this ADR exists
to respect.

**A path argument — `look(at: "~/Desktop/photo.png")`.** The model choosing a
file to read is the same defect as the model choosing an executable. If reading
an image from disk is ever wanted, the file is chosen by a person in a picker,
and it arrives the way a frame does.

**Keeping the vision model resident.** It would evict the router from memory,
and every voice turn afterwards would pay 7.5 s to bring it back. The camera is
used a few times a day; the router is used every turn.

**Storing frames to make answers reviewable.** A journal of pictures of
someone's room is a much larger thing than a journal of what they asked for.
The question and the answer are in the trail; the picture is not.
