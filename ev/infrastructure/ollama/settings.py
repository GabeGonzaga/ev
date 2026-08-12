"""Which model answers, per role, and how it is called.

The model is configuration, never a constant in the code. Swapping one out --
for a newer version, a different family, or a bake-off between two -- is an
edit to `models.json` or a `--model` flag, not a code change.

Roles exist because the two paths ask for different things: the router wants a
short structured answer as fast as possible, generation wants prose. Pointing
them at the same model is the default and the cheapest. Pointing them at
different ones is allowed and costs a weight swap per turn, which is why
`CLAUDE.md` prefers one resident model -- a cost to accept knowingly, not a
rule the code enforces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SETTINGS_FILE = "models.json"

Role = Literal["router", "generation", "vision"]

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"
"""A default, not a requirement. 8B keeps the interactive path inside the
latency budget; anything installed can replace it."""

DEFAULT_VISION_MODEL = "gemma3:12b"
"""Bigger than the 9B ceiling, and allowed to be.

`CLAUDE.md` puts that ceiling on the interactive path and says a larger model
may exist for non-interactive work, provided it is never the voice brain. This
one is asked a question about one frame, a few times a day, and is unloaded
immediately afterwards."""


class ModelSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    think: bool = False
    """Reasoning models deliberate before answering. Useful for hard problems,
    fatal for a router on a 900 ms budget."""

    keep_alive: str = "30m"
    """Long, because a reload costs more than every other stage combined."""

    timeout: float = 30.0


class RoutingSettings(BaseModel):
    """How much of the model's self-assessment to believe.

    Defaults, not findings. A model rating an invented call at 0.5 is exactly
    what these numbers exist to catch, and `make eval` is what moves them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    accept_at: float = Field(default=0.7, ge=0.0, le=1.0)
    clarify_at: float = Field(default=0.4, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.clarify_at > self.accept_at:
            raise ValueError("clarify_at must not exceed accept_at")
        return self


class OllamaSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = DEFAULT_HOST
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    router: ModelSettings = Field(
        default_factory=lambda: ModelSettings(name=DEFAULT_MODEL)
    )
    generation: ModelSettings = Field(
        default_factory=lambda: ModelSettings(name=DEFAULT_MODEL)
    )
    vision: ModelSettings = Field(
        # keep_alive "0" is the rule from the latency budget expressed as
        # configuration: load the vision model on capture, unload after.
        # Holding it would evict the router, and a cold router costs 7.5 s.
        default_factory=lambda: ModelSettings(
            name=DEFAULT_VISION_MODEL, keep_alive="0", timeout=120.0
        )
    )

    def for_role(self, role: Role) -> ModelSettings:
        if role == "router":
            return self.router
        return self.generation if role == "generation" else self.vision

    def models(self) -> list[str]:
        """Every distinct model this configuration needs resident.

        The vision model is not one of them: it is loaded when a frame arrives
        and unloaded when it has answered, so counting it here would have
        `make models` pull weights for something that is never held.
        """
        return sorted({self.router.name, self.generation.name})

    def with_model(self, name: str) -> Self:
        """Point the two resident roles at one model -- what `--model` does.

        Vision is left alone: `--model llama3.1:8b` is a bake-off between two
        routers, and pointing a camera at a model that cannot see would fail in
        a way that says nothing about either.
        """
        return self.model_copy(
            update={
                "router": self.router.model_copy(update={"name": name}),
                "generation": self.generation.model_copy(update={"name": name}),
            }
        )


def settings_path(state_dir: Path) -> Path:
    return state_dir / SETTINGS_FILE


def load_settings(path: Path) -> OllamaSettings:
    if not path.exists():
        return OllamaSettings()

    try:
        return OllamaSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        # Same reasoning as the permission grants: a malformed file is an error
        # with a path in it, not a silent fallback to defaults the user did not
        # ask for and cannot see.
        raise ValueError(f"{path}: {error}") from None


def save_settings(path: Path, settings: OllamaSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        settings.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
