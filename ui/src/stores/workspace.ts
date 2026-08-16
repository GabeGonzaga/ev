// Where each window is, and which of them is on top.
//
// Every widget is a window: the grid of slots this store was originally
// written for is gone, and with it the idea of a panel being "docked". What
// is left is geometry and stacking order, remembered in localStorage so a
// window opens where it was left rather than where it was born.

import { defineStore } from "pinia";
import { ref, watchEffect } from "vue";

export interface Floating {
  x: number;
  y: number;
  width: number;
  height: number;
}

/// `"docked"` survives only as the answer for a window nobody has placed
/// yet -- a widget that has never been opened has no geometry to report.
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

  /// Wholly on the display, and never smaller than a panel.
  ///
  /// Wholly, now: a window used to be allowed to hang off the right edge,
  /// which took its own resize handles with it. Applied on every write rather
  /// than only on drop, so a window can never be left somewhere it cannot be
  /// grabbed again.
  function clamp(where: Floating): Floating {
    const room = { wide: window.innerWidth, tall: window.innerHeight };
    const width = Math.min(Math.max(LEAST_WIDE, where.width), room.wide - MARGIN * 2);
    const height = Math.min(Math.max(LEAST_TALL, where.height), room.tall - MARGIN * 2);
    return {
      width,
      height,
      x: Math.min(Math.max(MARGIN, where.x), Math.max(MARGIN, room.wide - width - MARGIN)),
      y: Math.min(Math.max(MARGIN, where.y), Math.max(MARGIN, room.tall - height - MARGIN)),
    };
  }

  /// A window made smaller can strand one that was near an edge. Re-clamping
  /// every stored placement costs nothing and means the display is never
  /// holding a window somebody cannot reach.
  window.addEventListener("resize", () => {
    loose.value = Object.fromEntries(
      Object.entries(loose.value).map(([name, at]) => [name, clamp(at)]),
    );
  });


  return { loose, placement, isFloating, open, move, raise, depth };
});
