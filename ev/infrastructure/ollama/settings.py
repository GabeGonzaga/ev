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

Role = Literal["router", "generation"]

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"
"""A default, not a requirement. 8B keeps the interactive path inside the
latency budget; anything installed can replace it."""


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

    def for_role(self, role: Role) -> ModelSettings:
        return self.router if role == "router" else self.generation

    def models(self) -> list[str]:
        """Every distinct model this configuration needs resident."""
        return sorted({self.router.name, self.generation.name})

    def with_model(self, name: str) -> Self:
        """Point every role at one model -- what `--model` does for a run."""
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
