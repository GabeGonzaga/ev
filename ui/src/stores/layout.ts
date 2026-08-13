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

  /// Which widgets are on screen right now. Each one says so as it mounts,
  /// because a focus on a widget that no longer exists is a display with
  /// nothing on it and no way back -- which is exactly what happened when
  /// giving the floor to a widget hid the column it lived in.
  const present = ref<string[]>([]);

  function register(label: string) {
    if (!present.value.includes(label)) present.value = [...present.value, label];
  }

  function forget(label: string) {
    present.value = present.value.filter((name) => name !== label);
  }

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
    // A widget with the floor is never folded: it would be a widget with the
    // whole display and nothing in it.
    if (focused.value) folded.value = folded.value.filter((n) => n !== label);
  }

  /// Forget a focus on a widget that is not among these.
  ///
  /// The trap this closes: a label saved by an older layout -- "Answer", when
  /// there was a panel by that name -- leaves every widget hidden, including
  /// the one whose button would give the display back. Nothing on screen can
  /// fix it, and it survives a restart because it is written down.
  function reconcile(labels: string[]) {
    if (focused.value !== null && !labels.includes(focused.value)) {
      focused.value = null;
    }
    folded.value = folded.value.filter((name) => labels.includes(name));
  }

  /// Give the display back. Bound to Escape as well as to the button, so
  /// there is always a way out that does not require finding anything.
  function release() {
    focused.value = null;
  }

  /// Whether a widget should be on screen at all: everything, unless one of
  /// them has been given the floor.
  const shown = (label: string) => focused.value === null || focused.value === label;

  return {
    folded,
    focused,
    present,
    register,
    forget,
    reconcile,
    isFolded,
    fold,
    focus,
    release,
    shown,
  };
});
