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
  // A question the core is waiting on. While this is set, a turn is parked on
  // the other side and nothing has run.
  const question = ref<{ tool: string; risk: string; arguments: Record<string, unknown> } | null>(null);
  const locale = ref<string>("pt-PT");

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

  async function refresh() {
    try {
      entries.value = (await api.history(20)).entries;
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
    state, heard, said, trouble, entries, locale, question,
    ask, speak, answer, refresh, choose,
  };
});
