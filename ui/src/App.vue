<script setup lang="ts">
// Which display this is.
//
// The HUD is the interface. The view that came before it is still reachable
// while its panels are being rebuilt one at a time -- an assistant that
// cannot be asked anything for a week is not a step forward. `?legacy` works
// in a browser tab; the app has no address bar, so ⌘⌥L switches there and
// the choice is remembered. Both go when the composer and the dock land.

import { onBeforeUnmount, onMounted, ref } from "vue";
import HudSurface from "./components/hud/HudSurface.vue";
import LegacyApp from "./LegacyApp.vue";

const KEY = "ev.legacy";

const legacy = ref(
  new URLSearchParams(location.search).has("legacy") ||
    localStorage.getItem(KEY) === "yes",
);

function onKey(event: KeyboardEvent) {
  // Two modifiers, because one is a chord somebody will hit by accident and
  // this swaps the entire interface.
  if (!(event.metaKey && event.altKey) || event.code !== "KeyL") return;
  event.preventDefault();
  legacy.value = !legacy.value;
  localStorage.setItem(KEY, legacy.value ? "yes" : "no");
}

onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <LegacyApp v-if="legacy" />
  <HudSurface v-else />
</template>
