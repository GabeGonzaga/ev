"""Model selection is configuration.

Swapping a model -- a newer version, another family, two side by side for a
bake-off -- must never be a code change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev.infrastructure.ollama.settings import (
    DEFAULT_MODEL,
    ModelSettings,
    OllamaSettings,
    load_settings,
    save_settings,
    settings_path,
)


def test_defaults_put_both_roles_on_one_model() -> None:
    settings = OllamaSettings()

    assert settings.router.name == DEFAULT_MODEL
    assert settings.generation.name == DEFAULT_MODEL
    # One resident model, so no swap between routing and generation.
    assert settings.models() == [DEFAULT_MODEL]


def test_the_router_does_not_think_by_default() -> None:
    # Reasoning before answering is fatal to a 900 ms budget.
    assert OllamaSettings().router.think is False


def test_roles_may_differ_and_that_costs_a_swap() -> None:
    # Allowed, and the cost is real: two models cannot both stay resident, so
    # every turn that uses both pays a reload.
    settings = OllamaSettings(
        router=ModelSettings(name="qwen3:8b"),
        generation=ModelSettings(name="translategemma:4b"),
    )

    assert settings.models() == ["qwen3:8b", "translategemma:4b"]


def test_with_model_repoints_every_role() -> None:
    # What --model does: a bake-off is a loop over this.
    settings = OllamaSettings().with_model("llama3.1:8b")

    assert settings.models() == ["llama3.1:8b"]


def test_with_model_keeps_the_rest_of_each_role() -> None:
    settings = OllamaSettings(
        router=ModelSettings(name="qwen3:8b", timeout=9.0, keep_alive="1h")
    ).with_model("gemma3:12b")

    assert settings.router.timeout == 9.0
    assert settings.router.keep_alive == "1h"


def test_settings_round_trip(tmp_path: Path) -> None:
    path = settings_path(tmp_path)
    settings = OllamaSettings(
        router=ModelSettings(name="qwen3:8b", timeout=12.0),
        generation=ModelSettings(name="gemma3:12b"),
    )

    save_settings(path, settings)

    assert load_settings(path) == settings


def test_no_file_means_defaults(tmp_path: Path) -> None:
    assert load_settings(settings_path(tmp_path)) == OllamaSettings()


def test_a_malformed_file_names_the_path(tmp_path: Path) -> None:
    # Falling back to defaults would silently run a model the user did not pick.
    path = settings_path(tmp_path)
    path.write_text(json.dumps({"router": {"name": "x", "nonsense": 1}}))

    with pytest.raises(ValueError, match=str(path)):
        load_settings(path)
