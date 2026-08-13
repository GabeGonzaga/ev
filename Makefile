PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help test lint format install eval applescript protocol protocol-check rust app-check sign models ui app icons

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
	@echo "ui       typecheck and build the panel"
	@echo "app      build EV.app, then sign it with entitlements"
	@echo "models   download model weights and verify their checksums"
	@echo "icons    redraw the app and menu bar icons from icons/generate.py"
	@echo "applescript  run every AppleScript for real. Needs Music. NOT in CI"

test:
	$(PY) -m pytest

# osacompile proves syntax; this proves the scripts work. Needs a Mac with
# Music, so it is not a build gate either.
applescript:
	$(PY) -m evals.applescript

# Needs weights and is non-deterministic, so it is never a build gate.
eval:
	$(PY) -m evals.run $(ARGS)

CARGO ?= $(shell command -v cargo 2>/dev/null || echo $(HOME)/.cargo/bin/cargo)
HOST := native/target/release/ev-host

models:
	$(PY) models/download.py

models-check:
	$(PY) models/download.py --check

TSGEN := npx --yes json-schema-to-typescript@15

protocol:
	$(PY) -m protocol.export
	$(CARGO) typify --output protocol/generated/rust/protocol.rs \
		protocol/generated/ev.schema.json
	$(TSGEN) --input protocol/generated/ev.schema.json \
		--output protocol/generated/typescript/protocol.ts --bannerComment=

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

# The third view. Its toolchain is node, so it checks itself rather than being
# skipped when node is missing.
protocol-check-typescript:
	@$(TSGEN) --input protocol/generated/ev.schema.json \
		--output /tmp/ev.protocol.ts --bannerComment= >/dev/null
	@diff -q /tmp/ev.protocol.ts protocol/generated/typescript/protocol.ts \
		|| (echo "protocol/generated/typescript is stale. Run: make protocol"; exit 1)
	@echo "protocol.ts matches ev.schema.json"

IDENTITY ?= Apple Development: gggonzaga@icloud.com (AT55SB74NF)
APP := native/target/release/bundle/macos/EV.app

ui: protocol-check-typescript
	npm --prefix ui ci
	npm --prefix ui run build

# The icon is a program, not a picture: pure Python draws it and macOS's own
# iconutil packs it, so it can be changed by editing the thing that made it.
icons:
	$(PY) native/src-tauri/icons/generate.py

# The bundle is what gives E.V. its own TCC identity: launched from a shell the
# host borrows the terminal's grants, and only a bundled app gets an identity
# macOS decides about. Signing stays local; identities do not belong in CI.
app:
	cd native/src-tauri && $(CARGO) tauri build
	codesign --force --deep --options runtime --timestamp \
		--entitlements native/src-tauri/entitlements.plist \
		--sign "$(IDENTITY)" $(APP)
	codesign --verify --verbose=2 $(APP)

# The host, which is portable: its protocol client is plain Rust and its
# capture is cpal, so it builds anywhere ALSA headers exist. Linux is where
# nothing macOS-specific can hide, which is why it is worth building at all.
rust: protocol-check-rust
	cd native && $(CARGO) fmt --check
	cd native && $(CARGO) clippy -p ev-host --all-targets -- -D warnings
	cd native && $(CARGO) test -p ev-host
	cd native && $(CARGO) build -p ev-host --release

# The app is a macOS app: a menu bar, a panel, TCC, Apple Events. Building it
# on Linux would prove nothing and needs GTK and WebKit to prove it.
app-check:
	cd native && $(CARGO) clippy -p ev-app --all-targets -- -D warnings
	cd native && $(CARGO) test -p ev-app
	cd native && $(CARGO) build -p ev-app --release

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
