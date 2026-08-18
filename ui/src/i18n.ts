// The display's words, by key, in the language the session is set to.
//
// Not a framework -- forty lines, the same reasoning as the registry. There
// is one source of truth, `locales/en.json`: it is the file Ditto (the local
// translation service) ingests, and every other file in `locales/` was
// produced from it and dropped back in, never written by hand. Adding a
// language to the display is adding a file, not touching this.
//
// A key missing from the active locale falls back to English, and a key
// missing from English comes back as itself -- visible on the screen rather
// than swallowed, which is how a hole gets noticed.

import en from "./locales/en.json";
import { useAssistantState } from "./stores/assistant";

type Tree = { [key: string]: string | Tree };

/// Every locale file present is bundled. Vite resolves this at build time,
/// so a new language costs a rebuild and nothing else.
const SHELVES = import.meta.glob<{ default: Tree }>("./locales/*.json", {
  eager: true,
});

function shelf(locale: string): Tree | null {
  return SHELVES[`./locales/${locale}.json`]?.default ?? null;
}

function pick(tree: Tree, path: string): string | null {
  let node: string | Tree = tree;
  for (const part of path.split(".")) {
    if (typeof node === "string" || node[part] === undefined) return null;
    node = node[part];
  }
  return typeof node === "string" ? node : null;
}

/// The words for `key`, in the display's language.
///
/// Reads the store's locale on every call, so anything rendering through
/// this re-renders when the language changes. `{name}` params are
/// interpolated; a placeholder is structure, so a param the caller did not
/// pass stays visible in its braces rather than vanishing (the same rule
/// Ditto's validation gate enforces on the other side).
export function t(key: string, params?: Record<string, string | number>): string {
  const ev = useAssistantState();
  const spoken = shelf(ev.locale);
  const found = (spoken && pick(spoken, key)) ?? pick(en as Tree, key) ?? key;
  if (!params) return found;
  return found.replace(/\{(\w+)\}/g, (whole, name) =>
    name in params ? String(params[name]) : whole,
  );
}
