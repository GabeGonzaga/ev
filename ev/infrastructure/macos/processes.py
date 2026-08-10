"""The one door to a subprocess.

Every adapter that runs an executable goes through here. The signature is the
enforcement of invariant 2: argv is a list, never a string; there is no shell,
no `cwd`, no `env`, no redirection. A caller cannot ask for any of them, so a
tool argument cannot become any of them.

The executable is resolved on PATH rather than hardcoded, which is what makes
`tests/fakes/bin/` work -- the suite asserts on the exact argv that reaches
this boundary without mocking `subprocess`.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class CompletedProcess:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ProcessNotFound(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"executable not found on PATH: {name}")
        self.name = name


class ProcessFailed(Exception):
    def __init__(self, completed: CompletedProcess) -> None:
        detail = completed.stderr.strip() or completed.stdout.strip()
        message = f"{completed.argv[0]} exited {completed.returncode}"
        super().__init__(f"{message}: {detail}" if detail else message)
        self.completed = completed


class ProcessRunner:
    async def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        check: bool = True,
    ) -> CompletedProcess:
        if not argv:
            raise ValueError("argv must not be empty")

        executable = shutil.which(argv[0])
        if executable is None:
            raise ProcessNotFound(argv[0])

        process = await asyncio.create_subprocess_exec(
            executable,
            *argv[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            # Leaving it running would hold the pipes and outlive the turn.
            process.kill()
            await process.wait()
            raise

        completed = CompletedProcess(
            argv=tuple(argv),
            returncode=process.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )

        if check and completed.returncode != 0:
            raise ProcessFailed(completed)

        return completed
