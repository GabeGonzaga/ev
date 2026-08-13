<script setup lang="ts">
import { computed } from "vue";
import type { State } from "../stores/session";

const props = defineProps<{ state: State; ambient?: boolean }>();

/// 48 ticks, as angles, each with an opacity of its own. Drawn rather than
/// repeated in the template so the crown can be re-spaced by changing one
/// number -- and so the unevenness is deliberate rather than an accident of
/// hand-written markup.
const TICKS = 48;

const ticks = Array.from({ length: TICKS }, (_, index) => ({
  angle: (index * 360) / TICKS,
  /// Every fourth reaches further, the way a dial is marked.
  long: index % 4 === 0,
  /// A fixed, uneven pattern rather than random: it has to be the same on
  /// every render, or the crown shimmers when Vue re-draws it.
  dim: 0.28 + ((index * 37) % 11) / 18,
}));

// Idle turns at the described pace. Listening and thinking turn faster,
// because the ring is the one thing on screen that says "it is doing
// something" from across the room.
const pace = computed(() =>
  props.state === "idle" ? 1 : props.state === "speaking" ? 0.6 : 0.34,
);
</script>

<template>
  <div class="core" :class="[state, { ambient }]" :style="{ '--pace': pace }">
    <svg viewBox="0 0 320 320" aria-hidden="true">
      <defs>
        <!-- Electric blue, going cyan at the top. -->
        <linearGradient id="ring" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgb(var(--ring-top))" />
          <stop offset="100%" stop-color="rgb(var(--accent))" />
        </linearGradient>
      </defs>

      <!-- The halo: a wide, soft copy of the ring underneath it, breathing. -->
      <circle class="halo" cx="160" cy="160" r="110" />
      <circle class="ring" cx="160" cy="160" r="110" />

      <!-- A brighter arc, one turn every ten seconds. Slow enough to read as
           thought rather than as a thing waiting for a download. -->
      <circle class="arc" cx="160" cy="160" r="110" />

      <!-- And the crown, the other way at half the speed. -->
      <g class="crown">
        <line
          v-for="tick in ticks"
          :key="tick.angle"
          x1="160"
          :y1="tick.long ? 22 : 28"
          x2="160"
          y2="38"
          :style="{ opacity: tick.dim }"
          :transform="`rotate(${tick.angle} 160 160)`"
        />
      </g>

      <circle class="inner" cx="160" cy="160" r="86" />
    </svg>

    <div class="middle">
      <!-- Two letters and two periods, spaced as four beats rather than as
           words with punctuation in them. Kept small: the ring is what should
           be dominant, not the name inside it. -->
      <p class="wordmark" aria-label="E.V.">
        <span>E</span><span>.</span><span>V</span><span>.</span>
      </p>
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
  filter: blur(9px);
  animation: breathe 3s ease-in-out infinite;
}

.ring {
  fill: none;
  stroke: url(#ring);
  stroke-width: 1.6;
  opacity: 0.9;
}

.inner {
  fill: none;
  stroke: rgb(var(--accent));
  stroke-width: 0.75;
  opacity: 0.22;
}

/* A fifth of the circumference, near-white, ten seconds to the turn. */
.arc {
  fill: none;
  stroke: var(--ink);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-dasharray: 138 553;
  filter: drop-shadow(0 0 7px rgba(var(--accent), 0.9));
  transform-origin: 50% 50%;
  animation: turn calc(10s * var(--pace)) linear infinite;
}

.crown line {
  stroke: rgb(var(--accent));
  stroke-width: 1.4;
}

.crown {
  transform-origin: 50% 50%;
  /* The other way, at half the arc's speed. Two directions and two speeds
     read as depth; one of each reads as a spinner. */
  animation: turn calc(20s * var(--pace)) linear infinite reverse;
}

.middle {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  max-width: 54%;
  z-index: 1;
}

.wordmark {
  display: flex;
  /* The gap is the rhythm: a period is narrower than a letter, so letter
     spacing alone would leave the dots hanging closer to what precedes them. */
  gap: 0.2em;
  margin: 0;
  font-family: var(--display-font);
  font-size: 23px;
  font-weight: 200;
  letter-spacing: 0.16em;
  color: var(--text);
  text-shadow: 0 0 18px rgba(var(--accent), 0.7);
}

/* Alone on the screen, it can afford to be larger -- but only a little: the
   ring stays the thing you look at. */
.ambient .wordmark {
  font-size: 26px;
}

.ambient svg {
  width: min(420px, 60vmin);
}

/* Listening is the one state that should be legible with your back turned. */
.listening .ring {
  stroke: var(--live);
}

.listening .halo,
.listening .arc {
  stroke: var(--live);
}

@keyframes turn {
  to {
    transform: rotate(360deg);
  }
}

@keyframes breathe {
  0%,
  100% {
    opacity: 0.7;
  }
  50% {
    opacity: 1;
  }
}
</style>
