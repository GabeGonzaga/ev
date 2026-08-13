// Which widgets are open, and whether one of them has the floor.
//
// Remembered in localStorage: a display someone arranged should still be
// arranged tomorrow. Keyed by the widget's label, which is also what it is
// called on screen -- two names for one thing would be one too many.

import { defineStore } from "pinia";
import { ref, watchEffect } from "vue";

const FOLDED_KEY = "ev.folded";
const FOCUSED_KEY = "ev.focused";

function read<T>(key: string, fallback: T): T {
  try {
    const found = localStorage.getItem(key);
    return found === null ? fallback : (JSON.parse(found) as T);
  } catch {
    // A hand-edited or half-written value is not worth failing to start over.
    return fallback;
  }
}

export const useLayout = defineStore("layout", () => {
  const folded = ref<string[]>(read<string[]>(FOLDED_KEY, []));
  const focused = ref<string | null>(read<string | null>(FOCUSED_KEY, null));

  watchEffect(() => {
    localStorage.setItem(FOLDED_KEY, JSON.stringify(folded.value));
    localStorage.setItem(FOCUSED_KEY, JSON.stringify(focused.value));
  });

  const isFolded = (label: string) => folded.value.includes(label);

  function fold(label: string) {
    folded.value = isFolded(label)
      ? folded.value.filter((name) => name !== label)
      : [...folded.value, label];
    // Folded and focused at once is a widget that has the whole display and
    // shows nothing in it.
    if (focused.value === label && isFolded(label)) focused.value = null;
  }

  function focus(label: string) {
    focused.value = focused.value === label ? null : label;
    if (focused.value) folded.value = folded.value.filter((n) => n !== label);
  }

  /// Whether a widget should be on screen at all: everything, unless one of
  /// them has been given the floor.
  const shown = (label: string) => focused.value === null || focused.value === label;

  return { folded, focused, isFolded, fold, focus, shown };
});
