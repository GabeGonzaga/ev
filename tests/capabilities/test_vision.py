from __future__ import annotations

import json

import pytest

from ev.application.frames import Frames
from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.application.speech import Speaker
from ev.capabilities.vision.args import LookArgs
from ev.capabilities.vision.service import LOOK, VisionService
from ev.capabilities.vision.tools import vision_tools
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolErrorCode
from ev.domain.risk import RiskLevel
from ev.registry import CallRecord, Registry

FRAME = b"\xff\xd8\xff\xe0 not really a jpeg"


class Model:
    """A vision model that remembers what it was shown."""

    def __init__(self, answer: str = "A desk with a lamp on it.") -> None:
        self.answer = answer
        self.prompts: list[str] = []
        self.images: list[bytes] = []

    async def describe(self, prompt: str, image: bytes) -> str:
        self.prompts.append(prompt)
        self.images.append(image)
        return self.answer


class CollectingJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class Allowing:
    async def confirm(self, request: object) -> bool:
        return True


# --- the frame comes from a person, not from the model --------------------


def test_nothing_in_the_schema_names_an_image() -> None:
    """Invariant 8: the camera may not be started by ambiguous model
    inference. The model has no way to ask for a frame, only to be given one.
    """
    assert set(LookArgs.model_json_schema()["properties"]) == {"question"}


@pytest.mark.asyncio
async def test_with_no_frame_it_says_so_rather_than_describing_a_room() -> None:
    frames = Frames()
    service = VisionService(frames, Model(), Speaker("en"))

    result = await service.look(LookArgs())

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert "camera is not on" in result.error.message


@pytest.mark.asyncio
async def test_the_bound_frame_is_what_the_model_sees() -> None:
    frames = Frames()
    frames.bind(FRAME)
    model = Model()

    await VisionService(frames, model, Speaker("en")).look(LookArgs())

    assert model.images == [FRAME]


@pytest.mark.asyncio
async def test_a_question_is_asked_and_the_default_is_a_description() -> None:
    frames = Frames()
    frames.bind(FRAME)
    model = Model()
    service = VisionService(frames, model, Speaker("pt-PT"))

    await service.look(LookArgs(question="quantas chávenas há aqui?"))
    await service.look(LookArgs())

    assert "quantas chávenas" in model.prompts[0]
    assert "Descreve o que vês" in model.prompts[1]


@pytest.mark.asyncio
async def test_the_answer_is_asked_for_in_the_language_of_the_session() -> None:
    # A vision model given an English instruction answers in English however
    # it was spoken to.
    frames = Frames()
    frames.bind(FRAME)
    model = Model()

    await VisionService(frames, model, Speaker("pt-PT")).look(LookArgs())

    assert "português de Portugal" in model.prompts[0]


@pytest.mark.asyncio
async def test_the_answer_is_what_is_spoken() -> None:
    frames = Frames()
    frames.bind(FRAME)

    result = await VisionService(frames, Model("Uma secretária."), Speaker()).look(
        LookArgs()
    )

    assert result.ok
    assert result.speech == "Uma secretária."


@pytest.mark.asyncio
async def test_an_empty_answer_is_a_failure_not_a_silence() -> None:
    frames = Frames()
    frames.bind(FRAME)

    result = await VisionService(frames, Model("  \n "), Speaker("en")).look(LookArgs())

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED


# --- what the trail keeps -------------------------------------------------


@pytest.mark.asyncio
async def test_the_frame_never_reaches_the_journal() -> None:
    """Invariant 8: frames are not persisted.

    The journal records what was asked and what was said. The picture is not
    an argument, so there is nothing of it to write down.
    """
    frames = Frames()
    frames.bind(FRAME)
    journal = CollectingJournal()
    registry = Registry(
        policy=PermissionPolicy(
            PermissionLedger({Permission.CAMERA: PermissionState.GRANTED})
        ),
        confirmation=Allowing(),
        journal=journal,
    )
    for spec in vision_tools(VisionService(frames, Model(), Speaker("en"))):
        registry.register(spec)

    await registry.call(LOOK, {"question": "what is this?"})

    (record,) = journal.records
    assert record.arguments == {"question": "what is this?"}
    written = json.dumps(
        {"arguments": record.arguments, "data": record.result.data}, default=str
    )
    assert "jpeg" not in written
    assert str(FRAME) not in written


@pytest.mark.asyncio
async def test_a_frame_does_not_outlive_its_turn() -> None:
    frames = Frames()
    frames.bind(FRAME)

    assert frames.waiting
    frames.clear()

    assert frames.current() is None


# --- the permission -------------------------------------------------------


def test_looking_declares_the_camera() -> None:
    (spec,) = vision_tools(VisionService(Frames(), Model()))

    assert spec.name == LOOK
    assert spec.permissions == frozenset({Permission.CAMERA})
    assert spec.risk is RiskLevel.SENSITIVE


@pytest.mark.asyncio
async def test_with_the_camera_refused_the_model_is_never_asked() -> None:
    # A frame that a refused tool still sent to a model would be the whole
    # point missed. Refused, not merely undecided: an undecided permission is
    # let through so macOS can ask (ADR 0032), and by the time a frame exists
    # macOS has already been asked -- the surface could not have captured it
    # otherwise.
    frames = Frames()
    frames.bind(FRAME)
    model = Model()
    registry = Registry(
        policy=PermissionPolicy(
            PermissionLedger({Permission.CAMERA: PermissionState.DENIED})
        ),
        confirmation=Allowing(),
        journal=CollectingJournal(),
    )
    for spec in vision_tools(VisionService(frames, model, Speaker("en"))):
        registry.register(spec)

    result = await registry.call(LOOK, {})

    assert not result.ok
    assert model.images == []
