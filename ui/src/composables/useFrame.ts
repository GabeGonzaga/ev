// The one animation loop.
//
// Every component that needs to be redrawn subscribes here instead of calling
// requestAnimationFrame itself. Two loops on one screen do not share a
// deadline: each is scheduled independently, each does its own layout read,
// and the browser has no way to know they wanted the same frame. One loop,
// one callback list, one place to stop.
//
// It also means the display can be frozen -- while a tab is in the
// background, while the machine is asked not to animate -- from one place
// rather than from each component's own idea of the rules.

import { onBeforeUnmount, onMounted } from "vue";

export type Frame = (now: number, delta: number) => void;

const listeners = new Set<Frame>();

/// 60fps, even where the display offers 120. The orb does not look better at
/// 120 and the fans have an opinion about it.
const MIN_DELTA = 1000 / 61;

let handle = 0;
let last = 0;

function tick(now: number) {
  handle = requestAnimationFrame(tick);

  const delta = now - last;
  if (delta < MIN_DELTA) return;
  last = now;

  for (const listener of listeners) listener(now, delta);
}

function start() {
  if (handle || !listeners.size || document.hidden) return;
  last = performance.now();
  handle = requestAnimationFrame(tick);
}

function stop() {
  cancelAnimationFrame(handle);
  handle = 0;
}

// A window nobody is looking at should not be drawing. rAF already throttles
// a background tab, but "throttles" is not "stops", and this display is meant
// to be left running all day.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stop();
  else start();
});

/// Draw on every frame, for as long as this component is mounted.
export function useFrame(fn: Frame): void {
  onMounted(() => {
    listeners.add(fn);
    start();
  });

  onBeforeUnmount(() => {
    listeners.delete(fn);
    if (!listeners.size) stop();
  });
}
