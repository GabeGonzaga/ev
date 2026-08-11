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
  const locale = ref<string>("pt-PT");

  function apply(result: api.TurnResult) {
    heard.value = result.heard;
    said.value = result.spoken;
    trouble.value =
      result.outcome === "not_understood"
        ? "I did not understand that."
        : result.error;
  }

  async function ask(text: string) {
    if (!text.trim()) return;
    state.value = "thinking";
    trouble.value = null;
    try {
      apply(await api.submit(text));
    } catch (error) {
      // An unreachable daemon is an operational fault, not a failure to
      // understand, and it says which.
      trouble.value = String(error);
    } finally {
      state.value = "idle";
      await refresh();
    }
  }

  async function speak() {
    state.value = "listening";
    trouble.value = null;
    heard.value = null;
    try {
      apply(await api.listen());
    } catch (error) {
      trouble.value = String(error);
    } finally {
      state.value = "idle";
      await refresh();
    }
  }

  async function refresh() {
    try {
      entries.value = (await api.history(20)).entries;
    } catch {
      // History is a nicety. Failing to read it must not bury the turn that
      // just happened.
    }
  }

  async function choose(tag: string) {
    locale.value = tag;
    await api.setLocale(tag);
  }

  return { state, heard, said, trouble, entries, locale, ask, speak, refresh, choose };
});
