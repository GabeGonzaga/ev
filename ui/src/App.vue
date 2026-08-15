<script setup lang="ts">
// Which display this is.
//
// The HUD is the interface. The view that came before it is still reachable
// with `?legacy` while its panels are being rebuilt one at a time -- an
// assistant that cannot be asked anything for a week is not a step forward,
// and this costs one line. It goes when ConversationPanel lands.

import HudSurface from "./components/hud/HudSurface.vue";
import LegacyApp from "./LegacyApp.vue";

const legacy = new URLSearchParams(location.search).has("legacy");
</script>

<template>
  <LegacyApp v-if="legacy" />
  <HudSurface v-else />
</template>
