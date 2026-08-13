<script setup lang="ts">
import type { State } from "../stores/session";

defineProps<{ state: State }>();
</script>

<template>
  <!-- What E.V. is doing, in the corner of the eye. Colour and motion say it
       before the word underneath is read; the word is there because colour
       alone is not something everyone can read. -->
  <span class="dot" :class="state" :title="state" />
</template>

<style scoped>
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--faint);
  flex: none;
}

.listening {
  background: var(--live);
  animation: pulse 1.2s ease-in-out infinite;
}

.thinking {
  background: var(--accent);
  animation: pulse 1.6s ease-in-out infinite;
}

.speaking {
  background: var(--accent);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
</style>
