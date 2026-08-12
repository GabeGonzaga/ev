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
  outcome: "ran" | "unsure" | "not_understood" | "confirm" | string;
  speech?: string | null;
  error?: string | null;
  // Present only when outcome is "confirm": the turn is parked, waiting.
  tool?: string;
  risk?: string;
  arguments?: Record<string, unknown>;
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

/// Answering a question the core asked mid-turn. The page decides nothing on
/// the user's behalf: this only carries what they clicked.
///
/// The two shells differ in where the answer lands. In a browser the turn was
/// returned to us as a question, so answering it produces the outcome. In the
/// app the original call is still pending and resolves with the outcome
/// itself, so there is nothing to return here.
export const confirm = async (granted: boolean): Promise<TurnResult | null> => {
  if (inTauri) {
    await callTauri<void>("confirm", { granted });
    return null;
  }
  return http<TurnResult>("/api/confirm", {
    method: "POST",
    body: JSON.stringify({ granted }),
  });
};

/// In the app a question arrives as an event while the turn waits. In a
/// browser it arrives as the turn's own answer, so there is nothing to
/// subscribe to.
export async function onQuestion(
  handle: (question: Record<string, unknown>) => void,
): Promise<void> {
  if (!inTauri) return;
  const { listen } = await import("@tauri-apps/api/event");
  await listen<Record<string, unknown>>("confirmation.required", (event) =>
    handle(event.payload),
  );
}
