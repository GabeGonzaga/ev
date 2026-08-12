// Everything the panel can ask for, in either shell.
//
// One Vue application, two transports: Tauri commands when it is embedded in
// the app, fetch when it is served to a browser. The window never opens a
// socket and never executes anything either way -- it asks the core, and
// Registry.call() is what authorises.

import type { JournalEntry } from "./protocol";

export interface TurnResult {
  heard?: string | null;
  spoken?: string[];
  ok?: boolean;
  outcome: "ran" | "unsure" | "not_understood" | string;
  speech?: string | null;
  error?: string | null;
}

const inTauri = "__TAURI_INTERNALS__" in window;

// The token arrives once, in the fragment, which browsers never send to a
// server. Read it, keep it for this tab only, and take it out of the address
// bar so it does not survive a copied URL.
function claimToken(): string {
  const fromHash = new URLSearchParams(location.hash.slice(1)).get("token");
  if (fromHash) {
    sessionStorage.setItem("ev.token", fromHash);
    window.history.replaceState(null, "", location.pathname);
    return fromHash;
  }
  return sessionStorage.getItem("ev.token") ?? "";
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const answer = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${claimToken()}`,
      ...(init?.headers ?? {}),
    },
  });

  if (answer.status === 401) {
    throw new Error("This page is not authorised. Reopen the link E.V. printed.");
  }
  if (!answer.ok) throw new Error(await answer.text());
  return (await answer.json()) as T;
}

async function callTauri<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(command, args);
}

export const submit = (text: string, locale: string | null) =>
  inTauri
    ? callTauri<TurnResult>("submit", { text })
    : http<TurnResult>("/api/turn", {
        method: "POST",
        body: JSON.stringify({ text, locale }),
      });

/// In the app the microphone belongs to the signed host. In a browser it
/// belongs to the browser, which asks in its own name -- and the audio takes
/// the same path either way.
export const listen = (wav: Blob | null, locale: string | null) =>
  inTauri
    ? callTauri<TurnResult>("listen")
    : (async () => {
        const bytes = new Uint8Array(await wav!.arrayBuffer());
        let binary = "";
        bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
        return http<TurnResult>("/api/audio", {
          method: "POST",
          body: JSON.stringify({ audio: btoa(binary), locale }),
        });
      })();

export const history = (limit = 20) =>
  inTauri
    ? callTauri<{ entries: JournalEntry[] }>("history", { limit })
    : http<{ entries: JournalEntry[] }>(`/api/history?limit=${limit}`);

export const setLocale = (locale: string | null) =>
  inTauri ? callTauri<void>("set_locale", { locale }) : Promise.resolve();

export const canRecordHere = !inTauri;
