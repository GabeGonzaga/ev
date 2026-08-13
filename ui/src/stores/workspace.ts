// What is open, and where it sits.
//
// One registry for widgets and surfaces, so the dock and a spoken command
// reach the same switch. The specification is explicit about that: a voice
// interface that fails in a noisy room needs a silent fallback, and two paths
// to the same state are two states that will disagree.

import { defineStore } from "pinia";
import { computed, ref } from "vue";

/// Tools float over the orb; canvases take the screen and dock it; live feeds
/// hide it entirely.
export type Panel = "console" | "chat" | "music";
export type Surface = "camera";
export type Thing = Panel | Surface;

const SURFACES: Thing[] = ["camera"];

export interface Placed {
  x: number;
  y: number;
}

export const useWorkspace = defineStore("workspace", () => {
  const open = ref<Thing[]>([]);
  const places = ref<Record<string, Placed>>({});
  /// Which widget was touched last, and therefore draws on top.
  const order = ref<Thing[]>([]);

  const isOpen = (thing: Thing) => open.value.includes(thing);

  /// The one surface that has the screen, if any. Only ever one: no tiling,
  /// no split view, no tabs.
  const surface = computed(() => open.value.find((thing) => SURFACES.includes(thing)));

  function show(thing: Thing) {
    if (SURFACES.includes(thing)) {
      // A canvas replaces the canvas before it.
      open.value = [...open.value.filter((item) => !SURFACES.includes(item)), thing];
    } else if (!isOpen(thing)) {
      open.value = [...open.value, thing];
    }
    raise(thing);
  }

  function hide(thing: Thing) {
    open.value = open.value.filter((item) => item !== thing);
  }

  function toggle(thing: Thing) {
    isOpen(thing) ? hide(thing) : show(thing);
  }

  function raise(thing: Thing) {
    order.value = [...order.value.filter((item) => item !== thing), thing];
  }

  const depth = (thing: Thing) => 10 + order.value.indexOf(thing);

  function place(thing: Thing, at: Placed) {
    places.value = { ...places.value, [thing]: at };
  }

  return { open, places, isOpen, surface, show, hide, toggle, raise, depth, place };
});
