PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help test lint format install eval protocol protocol-check rust sign models

help:
	@echo "test     run the suite (must pass on Linux and macOS alike)"
	@echo "lint     ruff + mypy"
	@echo "format   ruff format"
	@echo "install  install dev dependencies into the active environment"
	@echo "eval     golden routing and translation evals. Needs Ollama. NOT in CI"
	@echo "         make eval ARGS='--model qwen3:8b --model llama3.1:8b'"
	@echo "protocol regenerate protocol/generated/ from protocol/messages.py"
	@echo "rust     fmt, clippy, test and build the native host. Needs cargo"
	@echo "sign     code-sign the host with your Apple Development identity"
	@echo "models   download model weights and verify their checksums"

test:
	$(PY) -m pytest

# Needs weights and is non-deterministic, so it is never a build gate.
eval:
	$(PY) -m evals.run $(ARGS)

CARGO ?= $(shell command -v cargo 2>/dev/null || echo $(HOME)/.cargo/bin/cargo)
HOST := native/target/release/ev-host

models:
	$(PY) models/download.py

models-check:
	$(PY) models/download.py --check

protocol:
	$(PY) -m protocol.export
	$(CARGO) typify --output protocol/generated/rust/protocol.rs \
		protocol/generated/ev.schema.json

# Each toolchain checks its own view of the artifact. Neither skips quietly if
# the other is missing: that is how three languages drift apart.
protocol-check:
	$(PY) -m protocol.export --check

protocol-check-rust:
	@$(CARGO) typify --output /tmp/ev.protocol.rs \
		protocol/generated/ev.schema.json
	@diff -q /tmp/ev.protocol.rs protocol/generated/rust/protocol.rs \
		|| (echo "protocol/generated/rust is stale. Run: make protocol"; exit 1)
	@echo "protocol.rs matches ev.schema.json"

rust: protocol-check-rust
	cd native && $(CARGO) fmt --check
	cd native && $(CARGO) clippy --all-targets -- -D warnings
	cd native && $(CARGO) test
	cd native && $(CARGO) build --release

# Local only. TCC keys its grants to a code signature, so an unsigned host is
# re-prompted on every rebuild. Signing identities do not belong in CI.
sign: rust
	codesign --force --options runtime --timestamp \
		--sign "Apple Development: gggonzaga@icloud.com (AT55SB74NF)" $(HOST)
	codesign --verify --verbose=2 $(HOST)

lint: protocol-check
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy

format:
	$(PY) -m ruff format .

install:
	$(PY) -m pip install -e ".[dev]"
