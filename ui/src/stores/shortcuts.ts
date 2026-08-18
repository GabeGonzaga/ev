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
  /// The site itself, as it was typed. Kept as a link rather than as a
  /// sentence so it can be opened more than one way -- the display decides
  /// how, the core decides whether.
  url: string;
}

const KEY = "ev.shortcuts";

const FIRST: Shortcut[] = [
  { id: 1, label: "github", url: "github.com" },
  { id: 2, label: "mail", url: "mail.google.com" },
];

/// What was stored before the link had a field of its own: a whole sentence,
/// `open github.com`. The verb comes off and the rest is the link.
interface Older {
  id: number;
  label: string;
  says?: string;
  url?: string;
}

function asLink(saved: Older): Shortcut {
  const url = saved.url ?? (saved.says ?? "").replace(/^\s*(open|abre|abrir)\s+/i, "");
  return { id: saved.id, label: saved.label, url: url.trim() };
}

function read(): Shortcut[] {
  try {
    const found = localStorage.getItem(KEY);
    if (!found) return FIRST;
    return (JSON.parse(found) as Older[]).map(asLink).filter((one) => one.url);
  } catch {
    // A hand-edited or half-written value is not worth failing to start over.
    return FIRST;
  }
}

export const useShortcuts = defineStore("shortcuts", () => {
  const saved = ref<Shortcut[]>(read());

  watchEffect(() => localStorage.setItem(KEY, JSON.stringify(saved.value)));

  function add(label: string, url: string) {
    const link = url.trim().replace(/^\s*(https?:\/\/)?/i, "");
    // A label is a convenience; the link is the shortcut. Missing one, the
    // link stands in for it.
    const named = label.trim() || link;
    if (!link) return;
    const id = Math.max(0, ...saved.value.map((each) => each.id)) + 1;
    saved.value = [...saved.value, { id, label: named, url: link }];
  }

  function forget(id: number) {
    saved.value = saved.value.filter((each) => each.id !== id);
  }

  return { saved, add, forget };
});
