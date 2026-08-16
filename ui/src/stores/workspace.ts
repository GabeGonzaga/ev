// Where each panel is: in its slot, or out on its own.
//
// Docked and floating are two placements of one panel, not two kinds of
// panel. The frame is identical either way -- what changes is whether the
// grid decides the geometry or the person does.
//
// Remembered in localStorage, and reconciled against the panels that actually
// exist on every start. A remembered name that no longer exists is how the
// old view once put a widget on the floor and lost the way back to it, and
// the fix is cheap enough to do before it happens again.

import { defineStore } from "pinia";
import { computed, ref, watchEffect } from "vue";

export interface Floating {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type Placement = "docked" | Floating;

const KEY = "ev.workspace";

/// Small enough to be worth floating, big enough to still be a panel.
export const LEAST_WIDE = 260;
export const LEAST_TALL = 160;

/// A floating panel stays this far inside the display, so the header -- which
/// is the only way to move it -- can never be dragged out of reach.
const MARGIN = 24;

function read(): Record<string, Floating> {
  try {
    const found = localStorage.getItem(KEY);
    return found ? (JSON.parse(found) as Record<string, Floating>) : {};
  } catch {
    // A hand-edited or half-written value is not worth failing to start over.
    return {};
  }
}

export const useWorkspace = defineStore("workspace", () => {
  /// Only the floating ones are in here. Absent means docked, which makes
  /// "docked" the state that needs no storage and no migration.
  const loose = ref<Record<string, Floating>>(read());
  /// Most recently raised last. Order rather than a z-index per panel: there
  /// is no number to keep unique and nothing to overflow.
  const raised = ref<string[]>([]);

  watchEffect(() => localStorage.setItem(KEY, JSON.stringify(loose.value)));

  /// Forget anything that is not a panel any more.
  function reconcile(names: readonly string[]) {
    const known = new Set(names);
    loose.value = Object.fromEntries(
      Object.entries(loose.value).filter(([name]) => known.has(name)),
    );
    raised.value = raised.value.filter((name) => known.has(name));
  }

  const floating = computed(() => Object.keys(loose.value));

  function placement(name: string): Placement {
    return loose.value[name] ?? "docked";
  }

  function isFloating(name: string): boolean {
    return name in loose.value;
  }

  /// Out of its slot, starting where it already is on screen -- so opening a
  /// panel looks like picking it up rather than like a new window appearing
  /// somewhere else.
  function open(name: string, from: Floating) {
    loose.value = { ...loose.value, [name]: clamp(from) };
    raise(name);
  }

  function dock(name: string) {
    const { [name]: _gone, ...rest } = loose.value;
    loose.value = rest;
    raised.value = raised.value.filter((each) => each !== name);
  }

  function toggle(name: string, from: Floating) {
    if (isFloating(name)) dock(name);
    else open(name, from);
  }

  function move(name: string, to: Floating) {
    if (!(name in loose.value)) return;
    loose.value = { ...loose.value, [name]: clamp(to) };
  }

  function raise(name: string) {
    raised.value = [...raised.value.filter((each) => each !== name), name];
  }

  /// How far up the stack, for the panel's z-index.
  function depth(name: string): number {
    const at = raised.value.indexOf(name);
    return at === -1 ? 0 : at + 1;
  }

  /// Inside the display, and never smaller than a panel. Applied on every
  /// write rather than only on drop, so a window resized smaller than the
  /// panel cannot strand one off the edge.
  function clamp(where: Floating): Floating {
    const width = Math.max(LEAST_WIDE, where.width);
    const height = Math.max(LEAST_TALL, where.height);
    return {
      width,
      height,
      x: Math.min(Math.max(MARGIN - width + 120, where.x), window.innerWidth - MARGIN),
      y: Math.min(Math.max(0, where.y), window.innerHeight - MARGIN),
    };
  }

  /// Everything back in its slot. One key, and the way out of any arrangement
  /// that has gone wrong.
  function dockAll() {
    loose.value = {};
    raised.value = [];
  }

  return {
    loose,
    floating,
    placement,
    isFloating,
    open,
    dock,
    toggle,
    move,
    raise,
    depth,
    dockAll,
    reconcile,
  };
});
