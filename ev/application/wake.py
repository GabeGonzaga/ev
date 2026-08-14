"""Was that E.V.'s name, and what came after it.

The wake word is transcribed rather than pattern-matched. A keyword spotter
recognises one sound it was trained on; this recognises whatever the person
put in a file, in any of the languages whisper knows, without training
anything. That is the whole reason it works this way: the word is the user's
to choose, and "any word" and "a trained model per word" cannot both be true.

The cost is stated plainly in ADR 0037: while the wake loop runs, everything
said near the machine is transcribed on it. Nothing leaves, nothing is stored,
and nothing that did not begin with the name is journalled -- but the audio is
read, and pretending otherwise would be dishonest.

Nothing here touches a model, a socket or a file. It is the decision, and it
is the part that has to be right in eight languages and a noisy kitchen.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_NOISE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE = re.compile(r"\s+")

FILLER = ("hey", "ok", "okay", "olá", "ola", "oi", "eh", "ei", "hi", "hello")
"""What people put in front of a name without meaning anything by it.

"Hey E.V." and "E.V." are the same request. Stripped before matching so that a
user who writes `ev` in the settings is not surprised by the half of the time
they say hey first.
"""


def flatten(text: str) -> str:
    """Down to letters, digits and single spaces, accents kept.

    Accents survive because they are part of the word in pt-PT -- `avó` is not
    `avo` -- and because whisper writes them. Punctuation does not survive:
    whisper spells a two-letter name `E.V.`, `E.V`, or `EV` depending on the
    sentence around it, and the difference is nothing anybody said.
    """
    normalised = unicodedata.normalize("NFC", text)
    return _SPACE.sub(" ", _NOISE.sub(" ", normalised)).strip().casefold()


def spellings(word: str) -> set[str]:
    """The ways whisper is likely to write one name.

    A short name is the hard case, and `EV` is about the hardest there is:
    two letters, a third of a second, and a dozen plausible spellings. So the
    letters are accepted spaced or joined, which covers `E V`, `E.V.` and
    `EV`, and the rest is what the user adds by hand.
    """
    flat = flatten(word)
    if not flat:
        return set()

    joined = flat.replace(" ", "")
    spelled = {flat, joined}

    # Letter by letter, but only for a name short enough to be an initialism:
    # `E.V.` is written `E V` about half the time. Spelling out `jarvis` as
    # `j a r v i s` would only ever match somebody spelling it out.
    if len(joined) <= 3:
        spelled.add(" ".join(joined))

    return spelled


@dataclass(frozen=True)
class WakeWord:
    """The name, and what else counts as it."""

    word: str = "ev"
    also: tuple[str, ...] = ("evie", "eevee", "hev")
    """Other spellings of the same name, and the defaults are measured rather
    than guessed.

    Said into this machine's microphone, "E.V." comes back as `EV`, as `Evie`
    in Portuguese, and as `H-E-V` when "hey" runs into it. `heavy` is what
    "hey E.V." sometimes becomes and is deliberately absent: a name that is
    also an ordinary word wakes on "heavy rain tomorrow".

    Whatever a particular voice and a particular room produce goes here, and
    it is not something anyone can predict from a spelling."""

    enabled: bool = False
    """Off unless asked for. Always-on listening is a decision someone makes,
    not a default they discover."""

    _all: frozenset[str] = field(default_factory=frozenset, compare=False)

    def variants(self) -> set[str]:
        found = spellings(self.word)
        for extra in self.also:
            found |= spellings(extra)
        return {variant for variant in found if variant}


@dataclass(frozen=True, slots=True)
class Heard:
    """What a fragment of room audio turned out to be."""

    woke: bool
    """Whether the name was said at the start of it."""

    rest: str = ""
    """What followed the name, if anything. `EV, play Blonde` leaves
    `play Blonde`; a bare `EV` leaves nothing, which means the person is about
    to say something and E.V. should listen rather than guess."""


def hear(transcript: str, wake: WakeWord) -> Heard:
    """Did this begin with E.V.'s name.

    *Begin*, deliberately. A name in the middle of a sentence is somebody
    talking about E.V. rather than to it, and acting on "I was telling Ana
    that E.V. can play music" is the failure that makes people turn a wake
    word off and never turn it back on.
    """
    said = flatten(transcript)
    if not said:
        return Heard(woke=False)

    # "Hey E.V." and "E.V." are one request.
    for filler in FILLER:
        if said.startswith(f"{filler} "):
            said = said[len(filler) + 1 :]
            break

    for variant in sorted(wake.variants(), key=len, reverse=True):
        if said == variant:
            return Heard(woke=True)
        if said.startswith(f"{variant} "):
            return Heard(woke=True, rest=said[len(variant) + 1 :].strip())

    return Heard(woke=False)
