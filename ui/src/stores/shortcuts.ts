// The sites and commands the user put on the strip.
//
// Local, and only local: a shortcut is a line of text E.V. is asked to run,
// exactly as if it had been typed or spoken. Nothing here fetches anything --
// clicking one submits `open <site>` to the core, and the core decides.

import { defineStore } from "pinia";
import { ref, watchEffect } from "vue";

export interface Shortcut {
  id: number;
  label: string;
  /// What gets submitted. A command, not a URL: the core owns what "open"
  /// means, and a UI that assembles URLs is a UI that has opinions about the
  /// internet.
  says: string;
}

const KEY = "ev.shortcuts";

const FIRST: Shortcut[] = [
  { id: 1, label: "github", says: "open github.com" },
  { id: 2, label: "mail", says: "open mail.google.com" },
];

function read(): Shortcut[] {
  try {
    const found = localStorage.getItem(KEY);
    return found ? (JSON.parse(found) as Shortcut[]) : FIRST;
  } catch {
    // A hand-edited or half-written value is not worth failing to start over.
    return FIRST;
  }
}

export const useShortcuts = defineStore("shortcuts", () => {
  const saved = ref<Shortcut[]>(read());

  watchEffect(() => localStorage.setItem(KEY, JSON.stringify(saved.value)));

  function add(label: string, says: string) {
    const clean = label.trim();
    const command = says.trim();
    if (!clean || !command) return;
    const id = Math.max(0, ...saved.value.map((each) => each.id)) + 1;
    saved.value = [...saved.value, { id, label: clean, says: command }];
  }

  function forget(id: number) {
    saved.value = saved.value.filter((each) => each.id !== id);
  }

  return { saved, add, forget };
});
