// Where each floating widget sits, how big it is, and whether it is open.
//
// The column layout (`layout.ts`) stacks widgets in two tidy columns; this is
// the other arrangement -- free-floating windows over the grid, the ones you
// drag where you want them and close when you are done, the way the HUD in the
// design does. The two do not fight: a widget is shown in one place or the
// other, and this store owns only the floating one.
//
// Remembered in localStorage, keyed by the window's id, so a display someone
// arranged is still arranged tomorrow. A geometry saved by an older build that
// names a window this one no longer has is dropped on reconcile, the same
// guard the column layout keeps.

import { defineStore } from "pinia";
import { reactive, watch } from "vue";

export interface Frame {
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  open: boolean;
}

/// What a window is when it is first opened and has no remembered place. Kept
/// with the window's definition, not here, so a new widget carries its own.
export interface Spawn {
  x: number;
  y: number;
  w: number;
  h: number;
  open?: boolean;
}

export const MIN_W = 240;
export const MIN_H = 120;

const KEY = "ev.windows";

function load(): Record<string, Frame> {
  try {
    const found = localStorage.getItem(KEY);
    return found ? (JSON.parse(found) as Record<string, Frame>) : {};
  } catch {
    // A hand-edited or half-written value is not worth failing to start over.
    return {};
  }
}

export const useWindows = defineStore("windows", () => {
  const frames = reactive<Record<string, Frame>>(load());
  // The next window to be touched goes on top. Seeded above whatever was
  // saved, so the first raise this session wins against yesterday's order.
  let top = Math.max(0, ...Object.values(frames).map((f) => f.z)) + 1;

  watch(
    frames,
    () => localStorage.setItem(KEY, JSON.stringify(frames)),
    { deep: true },
  );

  /// Make sure a window exists, giving it its spawn place the first time it is
  /// seen. Called by the window as it mounts, so a widget that was never
  /// opened costs nothing until it is.
  function define(id: string, spawn: Spawn): Frame {
    if (!frames[id]) {
      frames[id] = {
        x: spawn.x,
        y: spawn.y,
        w: spawn.w,
        h: spawn.h,
        z: top++,
        open: spawn.open ?? false,
      };
    }
    return frames[id];
  }

  const isOpen = (id: string) => frames[id]?.open ?? false;

  function open(id: string) {
    const frame = frames[id];
    if (frame) {
      frame.open = true;
      frame.z = top++;
    }
  }

  function close(id: string) {
    if (frames[id]) frames[id].open = false;
  }

  function toggle(id: string) {
    isOpen(id) ? close(id) : open(id);
  }

  /// Bring a window to the front. Every drag, resize, or click does this, so
  /// the one you are touching is the one you see.
  function raise(id: string) {
    if (frames[id]) frames[id].z = top++;
  }

  function moveTo(id: string, x: number, y: number) {
    const frame = frames[id];
    if (!frame) return;
    // Kept on screen by its title bar: a window dragged off the top or past a
    // side can always be caught again, because the bar you grab never leaves.
    const maxX = window.innerWidth - 48;
    const maxY = window.innerHeight - 40;
    frame.x = Math.min(Math.max(x, 8 - frame.w + 48), maxX);
    frame.y = Math.min(Math.max(y, 8), maxY);
  }

  function sizeTo(id: string, w: number, h: number) {
    const frame = frames[id];
    if (!frame) return;
    frame.w = Math.max(w, MIN_W);
    frame.h = Math.max(h, MIN_H);
  }

  /// Forget geometry for windows this build no longer has, and give the ones
  /// it does a fresh spawn if a broken value left them off screen.
  function reconcile(known: string[]) {
    for (const id of Object.keys(frames)) {
      if (!known.includes(id)) delete frames[id];
    }
  }

  return { frames, define, isOpen, open, close, toggle, raise, moveTo, sizeTo, reconcile };
});
