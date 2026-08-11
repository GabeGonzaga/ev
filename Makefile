PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help test lint format install eval protocol protocol-check

help:
	@echo "test     run the suite (must pass on Linux and macOS alike)"
	@echo "lint     ruff + mypy"
	@echo "format   ruff format"
	@echo "install  install dev dependencies into the active environment"
	@echo "eval     golden routing and translation evals. Needs Ollama. NOT in CI"
	@echo "         make eval ARGS='--model qwen3:8b --model llama3.1:8b'"
	@echo "protocol regenerate protocol/generated/ from protocol/messages.py"

test:
	$(PY) -m pytest

# Needs weights and is non-deterministic, so it is never a build gate.
eval:
	$(PY) -m evals.run $(ARGS)

protocol:
	$(PY) -m protocol.export

# Part of lint, so a stale artifact fails the build rather than the handshake.
protocol-check:
	$(PY) -m protocol.export --check

lint: protocol-check
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy

format:
	$(PY) -m ruff format .

install:
	$(PY) -m pip install -e ".[dev]"
