// Everything the panel can ask the app to do.
//
// The window never opens a socket. It calls the Rust side, which speaks the
// protocol -- the same rule the CLI follows and the same one CLAUDE.md states:
// the UI sends typed commands and never executes anything itself.

import { invoke } from "@tauri-apps/api/core";
import type { JournalEntry } from "./protocol";

export interface TurnResult {
  heard: string | null;
  spoken: string[];
  ok: boolean;
  outcome: "ran" | "unsure" | "not_understood" | string;
  error: string | null;
}

export const submit = (text: string) => invoke<TurnResult>("submit", { text });

export const listen = () => invoke<TurnResult>("listen");

export const setLocale = (locale: string | null) =>
  invoke<void>("set_locale", { locale });

export const history = (limit = 20) =>
  invoke<{ entries: JournalEntry[] }>("history", { limit });
