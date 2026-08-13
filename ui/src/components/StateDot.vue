<script setup lang="ts">
import type { State } from "../stores/session";

defineProps<{ state: State }>();
</script>

<template>
  <!-- What E.V. is doing, in the corner of the eye. Colour and motion say it
       before the word beside it is read; the word is there because colour
       alone is not something everyone can read. -->
  <span class="dot" :class="state" :title="state" />
</template>

<style scoped>
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  background: var(--faint);
  /* Square, like everything else here. A round light would be the only
     circle on screen. */
  box-shadow: 0 0 0 1px var(--line);
}

.listening {
  background: var(--live);
  box-shadow: 0 0 10px var(--live);
  animation: pulse 1.1s ease-in-out infinite;
}

.thinking {
  background: rgb(var(--accent));
  box-shadow: 0 0 10px rgba(var(--accent), 0.9);
  animation: pulse 1.6s ease-in-out infinite;
}

.speaking {
  background: var(--ink);
  box-shadow: 0 0 10px rgba(var(--accent), 0.9);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}
</style>
