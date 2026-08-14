"""`make models`: fetch model weights, and refuse anything that is not them.

Weights are never committed. They are large, they are not ours, and a
repository is not a cache. What *is* committed is the checksum, which is the
part that matters: a model file is code that runs on this machine, and
"downloaded from the internet" is not provenance.

The hashes below are the ones Hugging Face publishes for its own blobs, read
from its API rather than computed from whatever arrived first. A mismatch
deletes the file and fails.

    python models/download.py            the two models E.V. uses
    python models/download.py --check    verify what is already here
    python models/download.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"


@dataclass(frozen=True, slots=True)
class Model:
    name: str
    sha256: str
    megabytes: int
    why: str


# `small`, multilingual, not `base`: real input is mixed language -- "abre o
# Visual Studio Code" -- and base handles that badly.
DEFAULT = "ggml-small.bin"

WAKE = "ggml-tiny.bin"
"""What listens for the name. It only has to recognise one word, and it runs
on everything said in the room, so it is the small one."""

MODELS = {
    "ggml-small.bin": Model(
        name="ggml-small.bin",
        sha256="1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
        megabytes=488,
        why="what E.V. uses: small, multilingual",
    ),
    "ggml-small-q5_1.bin": Model(
        name="ggml-small-q5_1.bin",
        sha256="ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
        megabytes=190,
        why="quantised small, for measuring the accuracy cost",
    ),
    "ggml-tiny.bin": Model(
        name="ggml-tiny.bin",
        sha256="be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
        megabytes=78,
        why="the wake pass: every burst of room speech, so it has to be cheap",
    ),
    "ggml-base.bin": Model(
        name="ggml-base.bin",
        sha256="60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        megabytes=148,
        why="a floor to compare against, not for use",
    ),
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def verify(model: Model, path: Path) -> bool:
    found = digest(path)
    if found == model.sha256:
        print(f"  {model.name}: checksum matches")
        return True

    print(
        f"  {model.name}: CHECKSUM MISMATCH\n"
        f"    expected {model.sha256}\n"
        f"    found    {found}",
        file=sys.stderr,
    )
    return False


def fetch(model: Model) -> bool:
    path = HERE / model.name

    if path.exists():
        return verify(model, path)

    print(f"  {model.name}: downloading {model.megabytes} MB ({model.why})")
    # To a temporary name first: an interrupted download must not look like a
    # model, and the next run must not verify half a file.
    partial = path.with_suffix(path.suffix + ".partial")
    try:
        urllib.request.urlretrieve(f"{BASE}/{model.name}", partial)
    except OSError as error:
        partial.unlink(missing_ok=True)
        print(f"  {model.name}: download failed: {error}", file=sys.stderr)
        return False

    if digest(partial) != model.sha256:
        partial.unlink()
        print(
            f"  {model.name}: CHECKSUM MISMATCH after download. Deleted.",
            file=sys.stderr,
        )
        return False

    partial.rename(path)
    print(f"  {model.name}: verified")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Model weights, with checksums.")
    parser.add_argument("--all", action="store_true", help="every known model")
    parser.add_argument(
        "--check", action="store_true", help="verify what is here, download nothing"
    )
    arguments = parser.parse_args(argv)

    wanted = list(MODELS.values()) if arguments.all else [MODELS[DEFAULT], MODELS[WAKE]]
    print(f"models in {HERE}")

    ok = True
    for model in wanted:
        path = HERE / model.name
        if arguments.check:
            if not path.exists():
                print(f"  {model.name}: missing. Run: make models", file=sys.stderr)
                ok = False
            else:
                ok = verify(model, path) and ok
        else:
            ok = fetch(model) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
