<script setup lang="ts">
import { computed } from "vue";
import type { State } from "../stores/session";

const props = defineProps<{ state: State }>();

/// 48 ticks, as angles. Drawn rather than repeated in the template so the
/// crown can be re-spaced by changing one number.
const TICKS = 48;
const ticks = Array.from({ length: TICKS }, (_, index) => (index * 360) / TICKS);

/// Every fourth one reaches further, the way a dial is marked.
const long = (index: number) => index % 4 === 0;

// Idle turns slowly; listening and thinking turn faster. The ring is the one
// thing on screen that says "it is doing something" from across the room.
const pace = computed(() =>
  props.state === "idle" ? 1 : props.state === "speaking" ? 0.6 : 0.35,
);
</script>

<template>
  <div class="core" :class="state" :style="{ '--pace': pace }">
    <svg viewBox="0 0 320 320" aria-hidden="true">
      <!-- The halo: a wide, soft copy of the ring underneath it. -->
      <circle class="halo" cx="160" cy="160" r="110" />
      <circle class="ring" cx="160" cy="160" r="110" />

      <!-- A brighter arc, going one way. -->
      <circle class="arc" cx="160" cy="160" r="110" />

      <!-- And the crown of ticks, going the other. -->
      <g class="crown">
        <line
          v-for="(angle, index) in ticks"
          :key="angle"
          :class="{ long: long(index) }"
          x1="160"
          :y1="long(index) ? 22 : 28"
          x2="160"
          y2="38"
          :transform="`rotate(${angle} 160 160)`"
        />
      </g>

      <circle class="inner" cx="160" cy="160" r="86" />
    </svg>

    <div class="middle">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.core {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 0;
  flex: 1;
}

svg {
  position: absolute;
  width: min(320px, 92%);
  aspect-ratio: 1;
  pointer-events: none;
}

.halo {
  fill: none;
  stroke: rgb(var(--accent));
  stroke-width: 10;
  opacity: 0.18;
  filter: blur(9px);
}

.ring {
  fill: none;
  stroke: rgb(var(--accent));
  stroke-width: 1.5;
  opacity: 0.85;
}

.inner {
  fill: none;
  stroke: rgb(var(--accent));
  stroke-width: 0.75;
  opacity: 0.25;
}

/* A near-white arc: a fifth of the circumference, turning slowly. */
.arc {
  fill: none;
  stroke: var(--ink);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-dasharray: 138 553;
  filter: drop-shadow(0 0 6px rgba(var(--accent), 0.9));
  transform-origin: 50% 50%;
  animation: turn calc(14s * var(--pace)) linear infinite;
}

.crown line {
  stroke: rgb(var(--accent));
  stroke-width: 1.5;
  opacity: 0.45;
}

.crown line.long {
  opacity: 0.8;
}

.crown {
  transform-origin: 50% 50%;
  /* The other way, and slower: two speeds read as depth. */
  animation: turn calc(46s * var(--pace)) linear infinite reverse;
}

.middle {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  max-width: 54%;
  z-index: 1;
}

/* Listening is the one state that should be visible with your back turned. */
.listening .ring,
.listening .arc {
  stroke: var(--live);
}

.listening .halo {
  stroke: var(--live);
  opacity: 0.3;
}

@keyframes turn {
  to {
    transform: rotate(360deg);
  }
}
</style>
