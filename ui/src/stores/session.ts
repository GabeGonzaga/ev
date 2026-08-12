// What the panel knows: the turn in progress, and what has happened.

import { defineStore } from "pinia";
import { ref } from "vue";
import * as api from "../api";
import type { JournalEntry } from "../protocol";

export type State = "idle" | "listening" | "thinking" | "speaking";

export const useSession = defineStore("session", () => {
  const state = ref<State>("idle");
  const heard = ref<string | null>(null);
  const said = ref<string[]>([]);
  const trouble = ref<string | null>(null);
  const entries = ref<JournalEntry[]>([]);
  // The key that summons E.V., and whether the app took it. Empty in a
  // browser: a page cannot hold a global shortcut, and should not claim to.
  const shortcut = ref<string>("");
  const shortcutTrouble = ref<string | null>(null);
  // A question the core is waiting on. While this is set, a turn is parked on
  // the other side and nothing has run.
  const question = ref<{ tool: string; risk: string; arguments: Record<string, unknown> } | null>(null);
  const locale = ref<string>("pt-PT");
  // What the history is filtered by. Empty is the whole trail: a search box
  // someone cleared is not a search for nothing.
  const search = ref<string>("");

  function apply(result: api.TurnResult) {
    if (result.outcome === "confirm") {
      question.value = {
        tool: String(result.tool ?? ""),
        risk: String(result.risk ?? ""),
        arguments: (result.arguments ?? {}) as Record<string, unknown>,
      };
      return;
    }
    question.value = null;
    heard.value = result.heard ?? null;
    // The app returns the spoken lines; the web surface returns the result
    // itself. One shape here rather than two branches everywhere above.
    said.value = result.spoken ?? (result.speech ? [result.speech] : []);
    trouble.value =
      result.outcome === "not_understood"
        ? "I did not understand that."
        : (result.error ?? null);
  }

  async function ask(text: string) {
    if (!text.trim()) return;
    state.value = "thinking";
    trouble.value = null;
    try {
      apply(await api.submit(text, locale.value));
    } catch (error) {
      // An unreachable daemon is an operational fault, not a failure to
      // understand, and it says which.
      trouble.value = String(error);
    } finally {
      state.value = "idle";
      await refresh();
    }
  }

  async function speak(recording: Blob | null = null) {
    state.value = "listening";
    trouble.value = null;
    heard.value = null;
    try {
      apply(await api.listen(recording, locale.value));
    } catch (error) {
      trouble.value = String(error);
    } finally {
      state.value = "idle";
      await refresh();
    }
  }

  // In the app the question arrives while a turn waits; in a browser it comes
  // back as the turn's answer. One place to show it either way.
  void api.onQuestion((asked) => {
    question.value = {
      tool: String(asked.tool ?? ""),
      risk: String(asked.risk ?? ""),
      arguments: (asked.arguments ?? {}) as Record<string, unknown>,
    };
  });

  // A turn started by the hotkey, which the panel did not ask for and cannot
  // await. Same shape as any other turn once it arrives.
  void api.onHotkeyTurn(
    () => {
      state.value = "listening";
      heard.value = null;
      said.value = [];
      trouble.value = null;
    },
    (result) => {
      state.value = "idle";
      if (result) apply(result);
      void refresh();
    },
  );

  /// Take one frame and ask about it.
  ///
  /// The camera is on for as long as it takes to read a single frame and is
  /// stopped in a `finally`. `CLAUDE.md` invariant 8 asks for a visible
  /// active state and a session timeout; a session this short is the strongest
  /// form of both, and the browser shows its own indicator while it lasts.
  async function look(text: string | null = null) {
    if (!api.canSeeHere) return;
    state.value = "listening";
    trouble.value = null;

    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = document.createElement("video");
      video.srcObject = stream;
      video.muted = true;
      await video.play();
      // One frame, once the camera has actually produced one: the first is
      // often black while the sensor is still waking up.
      await new Promise((settle) => setTimeout(settle, 300));

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      const frame = canvas.toDataURL("image/jpeg", 0.8).split(",")[1] ?? "";

      state.value = "thinking";
      apply(await api.look(frame, text, locale.value));
    } catch (error) {
      trouble.value = String(error);
    } finally {
      stream?.getTracks().forEach((track) => track.stop());
      state.value = "idle";
      await refresh();
    }
  }

  async function load() {
    const saved = await api.settings();
    shortcut.value = saved.shortcut;
    if (saved.locale) locale.value = saved.locale;
  }

  async function bind(combination: string) {
    shortcutTrouble.value = null;
    try {
      await api.setShortcut(combination);
      shortcut.value = combination;
    } catch (error) {
      // The old one is still bound: the app registers the new key before it
      // forgets the old, so a combination another application owns costs
      // nothing.
      shortcutTrouble.value = String(error);
    }
  }

  async function refresh() {
    try {
      entries.value = (await api.history(20, search.value || null)).entries;
    } catch {
      // History is a nicety. Failing to read it must not bury the turn that
      // just happened.
    }
  }

  async function answer(granted: boolean) {
    const asked = question.value;
    question.value = null;
    if (!asked) return;
    state.value = "thinking";
    try {
      // Null in the app: the turn that asked is still pending and will
      // resolve with the outcome itself.
      const result = await api.confirm(granted);
      if (result) apply(result);
    } catch (error) {
      trouble.value = String(error);
    } finally {
      state.value = "idle";
      await refresh();
    }
  }

  async function choose(tag: string) {
    locale.value = tag;
    await api.setLocale(tag);
  }

  return {
    state, heard, said, trouble, entries, locale, question, search,
    shortcut, shortcutTrouble,
    ask, speak, look, answer, refresh, choose, load, bind,
  };
});
