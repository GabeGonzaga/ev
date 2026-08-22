<script setup lang="ts">
// Which display this is.
//
// The HUD is the interface. The view that came before it is still reachable
// while its panels are being rebuilt one at a time -- an assistant that
// cannot be asked anything for a week is not a step forward. `?legacy` works
// in a browser tab; the app has no address bar, so ⌘⌥L switches there.
//
// The choice is no longer remembered between launches, and that is the whole
// of this note. A remembered one is a trap: the app has no address bar and no
// menu item for it, so somebody who pressed the chord once -- or inherited it
// from a session they have forgotten -- opens the old view every launch
// afterwards with nothing on screen to say why, and no amount of pulling
// changes it, because the flag lives in the webview's storage rather than in
// the code. Opening on the HUD every time costs one chord to anyone who
// actually wants the old view, and costs nothing to everyone else.

import { onBeforeUnmount, onMounted, ref } from "vue";
import HudSurface from "./components/hud/HudSurface.vue";
import LegacyApp from "./LegacyApp.vue";

const legacy = ref(new URLSearchParams(location.search).has("legacy"));

function onKey(event: KeyboardEvent) {
  // Two modifiers, because one is a chord somebody will hit by accident and
  // this swaps the entire interface.
  if (!(event.metaKey && event.altKey) || event.code !== "KeyL") return;
  event.preventDefault();
  legacy.value = !legacy.value;
}

onMounted(() => {
  // An app stranded by the old build unstrands itself here rather than
  // needing a chord nobody can be expected to remember.
  localStorage.removeItem("ev.legacy");
  window.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <LegacyApp v-if="legacy" />
  <HudSurface v-else />
</template>
