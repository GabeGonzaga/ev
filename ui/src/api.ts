// Everything the panel can ask for, in either shell.
//
// One Vue application, two transports: Tauri commands when it is embedded in
// the app, fetch when it is served to a browser. The window never opens a
// socket and never executes anything either way -- it asks the core, and
// Registry.call() is what authorises.

import type { JournalEntry } from "./protocol";

export interface TurnResult {
  application?: string | null;
  assurance?: string;
  heard?: string | null;
  spoken?: string[];
  ok?: boolean;
  outcome: "ran" | "unsure" | "not_understood" | "confirm" | string;
  speech?: string | null;
  error?: string | null;
  /// Whatever the tool returned. A reading tool puts its answer here --
  /// `music.now_playing` its track and its cover -- and the payload already
  /// carried it, so nothing in the protocol had to change to let a widget
  /// draw one.
  data?: Record<string, unknown>;
  // Present only when outcome is "confirm": the turn is parked, waiting.
  tool?: string;
  risk?: string;
  arguments?: Record<string, unknown>;
}

const inTauri = "__TAURI_INTERNALS__" in window;

/// Which shell this is. The transports differ; nothing else should.
export const inApp = inTauri;

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
  if (!answer.ok) {
    // Only if it is ours. A static server, a proxy or a captive portal
    // answers with an HTML page, and printing that into a terminal-styled log
    // buries the one useful line under a document.
    const body = await answer.text();
    const ours = answer.headers.get("content-type")?.includes("json");
    throw new Error(
      ours ? body : `${answer.status} ${answer.statusText || "request failed"}`,
    );
  }
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

/// The trail, or a search of it. An empty query is the whole trail, which is
/// what an empty search box means.
export const history = (limit = 20, query: string | null = null) =>
  inTauri
    ? callTauri<{ entries: JournalEntry[] }>("history", { limit, query })
    : http<{ entries: JournalEntry[] }>(
        `/api/history?limit=${limit}` + (query ? `&q=${encodeURIComponent(query)}` : ""),
      );

/// One frame, and optionally what was said while looking at it.
///
/// The browser owns the camera here, exactly as it owns the microphone:
/// getUserMedia asks in the browser's name, the stream is stopped the moment
/// the frame is taken, and nothing is stored anywhere.
/// In the app the signed host opens the camera and takes the frame, so the
/// window never sees one. In a browser the page captures it and sends it,
/// because there getUserMedia asks in the browser's name.
export const look = (image: string | null, text: string | null, locale: string | null) =>
  inTauri
    ? callTauri<TurnResult>("look", { text })
    : http<TurnResult>("/api/vision", {
        method: "POST",
        body: JSON.stringify({ image, text, locale }),
      });

/// Whether the frame is taken here. False in the app: the host takes it.
export const capturesHere = !inTauri;
export const canSee = true;

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
/// What an answer also says about the application it was asked about.
/// `open` is "always", `blocked` is "never", null is "just this once".
export type Remember = "open" | "blocked" | null;

export const confirm = async (
  granted: boolean,
  remember: Remember = null,
): Promise<TurnResult | null> => {
  if (inTauri) {
    await callTauri<void>("confirm", { granted, remember });
    return null;
  }
  return http<TurnResult>("/api/confirm", {
    method: "POST",
    body: JSON.stringify({ granted, remember }),
  });
};

/// In the app a question arrives as an event while the turn waits. In a
/// browser it arrives as the turn's own answer, so there is nothing to
/// subscribe to.
export interface Wake {
  word: string;
  enabled: boolean;
}

/// What E.V. answers to. Only the app can change it: the file lives beside
/// the journal, and a browser tab has no business writing there.
export async function wakeState(): Promise<Wake | null> {
  if (!inTauri) return null;
  return callTauri<Wake>("wake_state");
}

export async function setWake(word: string, enabled: boolean): Promise<Wake> {
  return callTauri<Wake>("set_wake", { word, enabled });
}

/// The wake loop, while it runs.
///
/// A microphone that is open all day needs saying so where it can be seen.
/// The menu bar mark fills for as long as it is open; this is the same fact,
/// for a window that may or may not be on screen.
export async function onListening(
  live: (on: boolean) => void,
  woken: () => void,
): Promise<void> {
  if (!inTauri) return;
  const { listen } = await import("@tauri-apps/api/event");
  await listen<boolean>("wake.listening", (event) => live(event.payload));
  await listen("wake.woken", () => woken());
}

/// The camera, while it is on.
///
/// macOS shows its own indicator, and E.V. shows one too: a light that belongs
/// to the system does not say which application turned it on.
export async function onCamera(live: (on: boolean) => void): Promise<void> {
  if (!inTauri) return;
  const { listen } = await import("@tauri-apps/api/event");
  await listen("camera.started", () => live(true));
  await listen("camera.stopped", () => live(false));
}

/// A turn the panel did not start.
///
/// The hotkey records while a key is held, anywhere on the machine, and the
/// window is not awaiting anything when that happens -- so the app pushes what
/// it heard and what it did. In a browser there is no hotkey and nothing
/// subscribes.
export async function onHotkeyTurn(
  started: () => void,
  finished: (result: TurnResult | null) => void,
): Promise<void> {
  if (!inTauri) return;
  const { listen } = await import("@tauri-apps/api/event");
  await listen("turn.started", () => started());
  await listen("turn.cancelled", () => finished(null));
  await listen<TurnResult>("turn.completed", (event) => finished(event.payload));
}

/// The basemap, a byte range at a time.
///
/// A map is tiles, and tiles are normally a server: every pan tells somebody
/// where you are looking. This one is a single file on this machine -- the
/// PMTiles format is an archive addressed by range, so the renderer asks for
/// the few kilobytes covering the view and nothing else. The range comes
/// back through the same door as everything else: a command in the app, a
/// request on the local surface. No tile host, no key, no viewport leaving
/// the machine.
export const mapPresent = (): Promise<boolean> =>
  inTauri
    ? callTauri<boolean>("map_present")
    : fetch("/api/map", { method: "HEAD", headers: { Authorization: `Bearer ${claimToken()}` } })
        .then((answer) => answer.ok)
        .catch(() => false);

export async function mapRange(offset: number, length: number): Promise<ArrayBuffer> {
  if (inTauri) {
    return callTauri<ArrayBuffer>("map_range", { offset, length });
  }
  const answer = await fetch("/api/map", {
    headers: {
      Authorization: `Bearer ${claimToken()}`,
      // The one header that matters: without it this would pull a file that
      // can be gigabytes to draw one screen.
      Range: `bytes=${offset}-${offset + length - 1}`,
    },
  });
  if (!answer.ok) throw new Error(`the basemap refused a range: ${answer.status}`);
  return answer.arrayBuffer();
}

export interface Settings {
  shortcut: string;
  locale: string | null;
}

/// What the app remembers between launches. A browser page has no app to
/// remember anything, so it reports the defaults it cannot change.
export const settings = (): Promise<Settings> =>
  inTauri
    ? callTauri<Settings>("settings")
    : Promise.resolve({ shortcut: "", locale: null });

export const setShortcut = (shortcut: string) =>
  inTauri ? callTauri<void>("set_shortcut", { shortcut }) : Promise.resolve();

export const canBindKeys = inTauri;

/// Put the panel away. There is no window to hide in a browser tab.
export const dismiss = () =>
  inTauri ? callTauri<void>("dismiss") : Promise.resolve();

export type WindowAction = "minimise" | "fullscreen" | "close";

/// What the traffic lights would do, drawn by E.V. because the window has no
/// title bar to hang them from. A browser tab has its own and needs none.
export const windowControl = (action: WindowAction) =>
  inTauri ? callTauri<void>("window_control", { action }) : Promise.resolve();

export const hasWindowControls = inTauri;

export async function onQuestion(
  handle: (question: Record<string, unknown>) => void,
): Promise<void> {
  if (!inTauri) return;
  const { listen } = await import("@tauri-apps/api/event");
  await listen<Record<string, unknown>>("confirmation.required", (event) =>
    handle(event.payload),
  );
}
