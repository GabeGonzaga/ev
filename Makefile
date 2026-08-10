PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help test lint format install

help:
	@echo "test     run the suite (must pass on Linux and macOS alike)"
	@echo "lint     ruff + mypy"
	@echo "format   ruff format"
	@echo "install  install dev dependencies into the active environment"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy

format:
	$(PY) -m ruff format .

install:
	$(PY) -m pip install -e ".[dev]"
