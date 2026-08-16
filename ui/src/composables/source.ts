// Where a panel's data comes from, and the three ways that can go.
//
// Every panel has to render the same three outcomes -- waiting, failed, and
// something to show -- so every panel is handed the same shape and none of
// them gets to invent its own. A panel that only renders the happy path is a
// panel that hides a failure the first time one happens, and this display is
// supposed to be an instrument.
//
// Everything here is fake on purpose: no panel in this UI talks to the core
// yet. When one does, only the inside of its composable changes.

import { ref, type Ref } from "vue";

export interface Source<T> {
  /// What arrived, or null while it has not.
  data: Ref<T | null>;
  /// True until the first answer, and again for every reload.
  pending: Ref<boolean>;
  /// The failure, as a line to print. Never a boolean: a panel is expected
  /// to show what went wrong, and `true` cannot be shown.
  error: Ref<string | null>;
  reload: () => void;
}

export interface StubOptions {
  /// How long the fake answer takes. Not zero, because a loading state that
  /// never appears in development is a loading state nobody ever styles.
  latency?: number;
  /// The failure to produce instead of an answer. Set it to see a panel's
  /// error state; leave it out for the happy path.
  fails?: string;
}

/// A data source that makes something up, slowly, and sometimes fails.
export function stub<T>(produce: () => T, options: StubOptions = {}): Source<T> {
  const data = ref<T | null>(null) as Ref<T | null>;
  const pending = ref(true);
  const error = ref<string | null>(null);
  let timer = 0;

  function reload() {
    window.clearTimeout(timer);
    pending.value = true;
    error.value = null;

    timer = window.setTimeout(() => {
      pending.value = false;
      if (options.fails !== undefined) {
        error.value = options.fails;
        data.value = null;
        return;
      }
      data.value = produce();
    }, options.latency ?? 420);
  }

  reload();
  return { data, pending, error, reload };
}
