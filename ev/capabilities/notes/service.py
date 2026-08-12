"""Orchestration. Never touches the system directly.

One thing happens here that is not an adapter call: a spoken folder name is
matched against the folders that exist. `Trabalho / 2026` is not something
anyone dictates exactly, and creating a folder from a mishearing is worse than
refusing.
"""

from __future__ import annotations

from ev.application.speech import Speaker
from ev.capabilities.notes.adapters import NO_FOLDER, NotesAdapter
from ev.capabilities.notes.args import CreateArgs
from ev.domain.naming import closest
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applescript import AppleScriptError

CREATE = "notes.create"


class NotesService:
    def __init__(self, adapter: NotesAdapter, speaker: Speaker | None = None) -> None:
        self._adapter = adapter
        self._speaker = speaker or Speaker()

    async def create(self, args: CreateArgs) -> ToolResult:
        folder: str | None = None

        if args.folder is not None:
            existing = await self._adapter.folders()
            folder = closest(args.folder, existing)
            if folder is None:
                # Naming a few is the difference between "it did not work" and
                # knowing what to say instead.
                suggestions = ", ".join(existing[:5]) or "none"
                return ToolResult.failure(
                    CREATE,
                    ToolErrorCode.INVALID_ARGUMENTS,
                    self._speaker.say(
                        "notes.no_folder", name=args.folder, existing=suggestions
                    ),
                )

        try:
            title = await self._adapter.create(args.title, args.body, folder)
        except AppleScriptError as error:
            # The folder existed a moment ago and does not now. Nothing here
            # can recover from that, and it is worth saying plainly.
            code = (
                ToolErrorCode.INVALID_ARGUMENTS
                if NO_FOLDER in str(error)
                else ToolErrorCode.ADAPTER_FAILED
            )
            return ToolResult.failure(CREATE, code, str(error))

        return ToolResult.success(
            CREATE,
            data={"title": title, "folder": folder, "written": args.body is not None},
            speech=(
                self._speaker.say("notes.created_in", title=title, folder=folder)
                if folder
                else self._speaker.say("notes.created", title=title)
            ),
        )
