PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help test lint format install eval

help:
	@echo "test     run the suite (must pass on Linux and macOS alike)"
	@echo "lint     ruff + mypy"
	@echo "format   ruff format"
	@echo "install  install dev dependencies into the active environment"
	@echo "eval     golden routing and translation evals. Needs Ollama. NOT in CI"
	@echo "         make eval ARGS='--model qwen3:8b --model llama3.1:8b'"

test:
	$(PY) -m pytest

# Needs weights and is non-deterministic, so it is never a build gate.
eval:
	$(PY) -m evals.run $(ARGS)

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy

format:
	$(PY) -m ruff format .

install:
	$(PY) -m pip install -e ".[dev]"
