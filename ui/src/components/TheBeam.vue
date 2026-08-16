<script setup lang="ts">
import { ref, watch } from "vue";
import { useSession } from "../stores/session";

/// The sweep that answers the name.
///
/// When E.V. wakes -- the hotkey, the wake word, or a press-to-talk -- the
/// display comes alive with a single band of light that falls from the top of
/// the screen to the bottom, lighting the grid as it passes. It is the one
/// piece of motion that says "I heard you" before a word is transcribed.
///
/// It fires on the edge into `listening`, not while listening: a beam that
/// repeated every frame would be a strobe, not a greeting. One pass, then it
/// takes itself off screen until the next wake.
const session = useSession();
const sweeping = ref(false);

watch(
  () => session.state,
  (now, was) => {
    if (now === "listening" && was !== "listening") sweeping.value = true;
  },
);
</script>

<template>
  <!-- Rendered only while it sweeps, so it costs nothing at rest. The grid it
       lights is painted by the page behind it; this is only the light. -->
  <div
    v-if="sweeping"
    class="beam"
    aria-hidden="true"
    @animationend="sweeping = false"
  />
</template>

<style scoped>
.beam {
  position: fixed;
  inset: -20% 0 auto 0;
  height: 40%;
  z-index: 2;
  pointer-events: none;
  /* A soft vertical band: bright at its middle, gone at both edges, so it
     reads as a passing beam rather than a moving block. Additive over the
     dark, so it lights the grid instead of covering it. */
  background: linear-gradient(
    to bottom,
    transparent 0%,
    rgba(var(--accent), 0.06) 30%,
    rgba(var(--accent-lit), 0.28) 50%,
    rgba(var(--accent), 0.06) 70%,
    transparent 100%
  );
  mix-blend-mode: screen;
  filter: blur(2px);
  animation: fall 0.85s cubic-bezier(0.5, 0, 0.4, 1) 1;
}

/* From just above the screen to just below it: one clean pass. */
@keyframes fall {
  from {
    transform: translateY(0);
    opacity: 0;
  }
  12% {
    opacity: 1;
  }
  88% {
    opacity: 1;
  }
  to {
    transform: translateY(320vh);
    opacity: 0;
  }
}

/* In daylight the screen blend shows nothing on white, so it becomes a
   faint tinted band laid over the top instead. */
:root[data-theme="light"] .beam {
  mix-blend-mode: normal;
  background: linear-gradient(
    to bottom,
    transparent 0%,
    rgba(var(--accent), 0.1) 50%,
    transparent 100%
  );
}

/* Motion off: no sweep. The state still changes; the greeting is just quiet. */
@media (prefers-reduced-motion: reduce) {
  .beam {
    display: none;
  }
}
</style>
