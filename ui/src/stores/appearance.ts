// What E.V. looks like, and where that is remembered.
//
// Three axes: the theme (system, dark, light), the accent, and nothing else.
// They live in localStorage rather than in `app.json`, because a look is the
// window's business and not the core's -- the daemon should not have to be
// running for a page to know it is meant to be dark.

import { defineStore } from "pinia";
import { computed, ref, watchEffect } from "vue";

export type Theme = "system" | "dark" | "light";

/// The evolutions, plus E.V.'s own. One hue each; nothing else changes.
export const ACCENTS = [
  "cyan",
  "vaporeon",
  "jolteon",
  "flareon",
  "espeon",
  "umbreon",
  "leafeon",
  "glaceon",
  "sylveon",
] as const;

export type Accent = (typeof ACCENTS)[number];

const THEME_KEY = "ev.theme";
const ACCENT_KEY = "ev.accent";

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const found = localStorage.getItem(key) as T | null;
  return found && allowed.includes(found) ? found : fallback;
}

export const useAppearance = defineStore("appearance", () => {
  const theme = ref<Theme>(stored(THEME_KEY, ["system", "dark", "light"], "system"));
  const accent = ref<Accent>(stored(ACCENT_KEY, ACCENTS, "cyan"));

  // What the system is set to right now, kept live: "system" has to mean
  // system at four in the afternoon as well as at nine in the morning.
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const systemIsDark = ref(dark.matches);
  dark.addEventListener("change", (event) => (systemIsDark.value = event.matches));

  const resolved = computed(() =>
    theme.value === "system" ? (systemIsDark.value ? "dark" : "light") : theme.value,
  );

  // On <html>, so every rule can reach it without anything being passed down.
  watchEffect(() => {
    document.documentElement.dataset.theme = resolved.value;
    document.documentElement.dataset.accent = accent.value;
    localStorage.setItem(THEME_KEY, theme.value);
    localStorage.setItem(ACCENT_KEY, accent.value);
  });

  return { theme, accent, resolved };
});
