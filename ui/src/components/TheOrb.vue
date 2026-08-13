<script setup lang="ts">
import { computed } from "vue";

/// The six states. Everything the interface knows how to feel is one of
/// these, and the orb is where all of them are expressed.
export type Mood =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "confirm"
  | "error";

const props = withDefaults(
  defineProps<{ mood?: Mood; docked?: boolean; level?: number }>(),
  { mood: "idle", docked: false, level: 0 },
);

const RING = 100;

/// Tapered, like a brush stroke: thickest in the middle, points at both ends.
/// A uniform stroke looks mechanical, and these two arcs are most of what
/// makes the composition read as drawn rather than generated.
function crescent(radius: number, from: number, to: number, weight: number) {
  const steps = 28;
  const outer: string[] = [];
  const inner: string[] = [];

  for (let step = 0; step <= steps; step += 1) {
    const along = step / steps;
    const angle = ((from + (to - from) * along) * Math.PI) / 180;
    // A sine gives the taper: nothing at the ends, everything in the middle.
    const thickness = (Math.sin(along * Math.PI) * weight) / 2;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    outer.push(`${160 + cos * (radius + thickness)},${160 + sin * (radius + thickness)}`);
    inner.unshift(
      `${160 + cos * (radius - thickness)},${160 + sin * (radius - thickness)}`,
    );
  }

  return `M${outer.join("L")}L${inner.join("L")}Z`;
}

/// A thin arc with no taper, for the filaments.
function thread(radius: number, from: number, to: number) {
  const start = (from * Math.PI) / 180;
  const end = (to * Math.PI) / 180;
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return [
    `M${160 + Math.cos(start) * radius},${160 + Math.sin(start) * radius}`,
    `A${radius},${radius} 0 ${large} 1`,
    `${160 + Math.cos(end) * radius},${160 + Math.sin(end) * radius}`,
  ].join(" ");
}

const primary = [
  // Upper right, and lower left at a slightly larger radius.
  crescent(RING + 9, -70, 10, 5),
  crescent(RING + 16, 115, 195, 4.5),
];

/// Two or three hairlines, clustered on one side, at differing radii. Barely
/// visible on purpose: they are depth, not decoration.
const filaments = [
  { d: thread(RING + 24, -40, 30), opacity: 0.35 },
  { d: thread(RING + 33, -15, 55), opacity: 0.28 },
  { d: thread(RING + 41, 5, 70), opacity: 0.22 },
];

/// The only regular thing in the composition, and what anchors it: one short
/// radial mark at each cardinal, a tangential double-slash at each diagonal.
const cardinals = [0, 90, 180, 270];
const diagonals = [45, 135, 225, 315];

/// Scatter: irregular radii, irregular angles, clumps and gaps. Generated
/// once from a fixed seed -- random every render would shimmer, and evenly
/// spaced would look like a loading spinner, which is the one thing this must
/// never look like.
const scatter = (() => {
  let seed = 20260814;
  const random = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };

  return Array.from({ length: 42 }, () => {
    // Denser near the ring: squaring the roll pulls the crowd inward.
    const radius = RING * (1.15 + Math.pow(random(), 2) * 0.55);
    const angle = random() * 360;
    const dash = random() > 0.7;
    return {
      x: 160 + Math.cos((angle * Math.PI) / 180) * radius,
      y: 160 + Math.sin((angle * Math.PI) / 180) * radius,
      angle,
      dash,
      size: dash ? 2 + random() * 3.5 : 0.7 + random() * 1.3,
      opacity: 0.2 + random() * 0.5,
    };
  });
})();

/// Confirm stops everything dead. In a composition where nothing is ever
/// still, stillness is the loudest signal available.
const frozen = computed(() => props.mood === "confirm");

const pace = computed(() => {
  switch (props.mood) {
    case "thinking":
      return 1.5;
    case "speaking":
      return 40;
    case "listening":
      return 6;
    default:
      return 8;
  }
});

/// Listening pushes the halo out and brightens it with the room; speaking
/// modulates it to what is being said. Both arrive as a level from 0 to 1.
const halo = computed(() => {
  if (props.mood === "listening") return 1.15 + props.level * 0.25;
  if (props.mood === "speaking") return 1 + props.level * 0.2;
  if (props.mood === "thinking") return 0.92;
  return 1;
});
</script>

<template>
  <div
    class="orb"
    :class="[mood, { docked, frozen }]"
    :style="{ '--pace': `${pace}s`, '--halo': halo }"
  >
    <svg viewBox="0 0 320 320" aria-hidden="true">
      <defs>
        <radialGradient id="halo" cx="44%" cy="41%">
          <!-- Light spilling from behind the ring: nothing until the ring's
               edge, hottest just outside it, gone within about 40px. Brighter
               to the upper left, because a light source has a direction. -->
          <stop offset="62%" stop-color="rgba(var(--glow), 0)" />
          <stop offset="70%" stop-color="rgba(var(--glow-hot), 0.42)" />
          <stop offset="78%" stop-color="rgba(var(--glow), 0.26)" />
          <stop offset="92%" stop-color="rgba(var(--glow), 0)" />
        </radialGradient>

        <filter id="soften" x="-40%" y="-40%" width="180%" height="180%">
          <!-- Diffuse rather than banded: a gradient alone leaves visible
               steps where the stops are, and the eye finds them immediately. -->
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>

      <!-- The halo sits outside the ring and bleeds in. It is the only
           substantial blue in the composition. -->
      <circle
        class="halo"
        cx="160"
        cy="160"
        r="145"
        fill="url(#halo)"
        filter="url(#soften)"
      />

      <!-- A dark well, darker than the page: that is what makes the halo
           read as light spilling from behind it rather than as a hole. -->
      <circle class="core" cx="160" cy="160" :r="RING" />

      <!-- One crisp white circle, uniform weight the whole way round. All
           the softness in the picture comes from the halo, never from here. -->
      <circle class="ring" cx="160" cy="160" :r="RING" />

      <g class="arcs">
        <path v-for="(d, index) in primary" :key="index" class="crescent" :d="d" />
      </g>

      <g class="filaments">
        <path
          v-for="(filament, index) in filaments"
          :key="index"
          :d="filament.d"
          :style="{ opacity: filament.opacity }"
        />
      </g>

      <g class="marks">
        <line
          v-for="angle in cardinals"
          :key="`c${angle}`"
          x1="160"
          y1="10"
          x2="160"
          y2="22"
          :transform="`rotate(${angle} 160 160)`"
        />
        <g v-for="angle in diagonals" :key="`d${angle}`">
          <line
            x1="154"
            y1="12"
            x2="160"
            y2="24"
            :transform="`rotate(${angle} 160 160)`"
          />
          <line
            x1="162"
            y1="12"
            x2="168"
            y2="24"
            :transform="`rotate(${angle} 160 160)`"
          />
        </g>
      </g>

      <g class="scatter">
        <template v-for="(speck, index) in scatter" :key="index">
          <line
            v-if="speck.dash"
            :x1="speck.x"
            :y1="speck.y"
            :x2="speck.x + speck.size"
            :y2="speck.y"
            :transform="`rotate(${speck.angle + 90} ${speck.x} ${speck.y})`"
            :style="{ opacity: speck.opacity }"
          />
          <circle
            v-else
            :cx="speck.x"
            :cy="speck.y"
            :r="speck.size"
            :style="{ opacity: speck.opacity }"
          />
        </template>
      </g>
    </svg>

    <!-- Two letters and two periods, spaced as four beats. Large: it fills
         most of the interior, because a timid wordmark in a big ring looks
         like a placeholder. No glow -- flat white on a dark well, and the
         contrast does the work. -->
    <p class="wordmark" aria-label="E.V.">
      <span>E</span><span>.</span><span>V</span><span>.</span>
    </p>
  </div>
</template>

<style scoped>
.orb {
  position: relative;
  width: 460px;
  height: 460px;
  display: grid;
  place-items: center;
  transition: transform 600ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease;
}

svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.core {
  fill: var(--bg-deep);
}

.ring {
  fill: none;
  stroke: var(--ring);
  stroke-width: 1.8;
}

.halo {
  transform-origin: 50% 50%;
  transform: scale(var(--halo));
  transition: transform 220ms ease;
  animation: breathe 3s ease-in-out infinite;
}

.crescent {
  fill: var(--ring);
}

.arcs {
  transform-origin: 50% 50%;
  animation: turn var(--pace) linear infinite;
}

.filaments path {
  fill: none;
  stroke: var(--ring);
  stroke-width: 0.8;
}

.filaments {
  transform-origin: 50% 50%;
  /* The other way, and faster when thinking: counter-rotation is what stops
     the whole thing reading as one wheel. */
  animation: turn calc(var(--pace) * 2.4) linear infinite reverse;
}

.marks line {
  stroke: rgb(var(--tick));
  stroke-width: 1.2;
  opacity: 0.75;
}

.marks {
  transform-origin: 50% 50%;
  animation: turn 34s linear infinite;
}

.scatter line {
  stroke: rgb(var(--tick));
  stroke-width: 1;
}

.scatter circle {
  fill: rgb(var(--tick));
}

.scatter {
  transform-origin: 50% 50%;
  animation: turn 60s linear infinite reverse;
}

.wordmark {
  position: relative;
  display: flex;
  /* The gap is the rhythm: a period is narrower than a letter, so letter
     spacing alone leaves each dot hanging off what precedes it. */
  gap: 0.14em;
  margin: 0;
  font-family: var(--system);
  font-size: 36px;
  font-weight: 400;
  letter-spacing: 0.15em;
  color: var(--text);
}

/* Stillness, and arcs held exactly opposed. */
.frozen .arcs,
.frozen .filaments,
.frozen .marks,
.frozen .scatter,
.frozen .halo {
  animation: none;
}

.confirm .halo {
  filter: hue-rotate(-155deg) saturate(1.4);
}

.error .ring {
  animation: alarm 1.2s ease-out;
}

.error .halo {
  filter: hue-rotate(-175deg) saturate(1.6);
}

/* Docked: smaller, and still alive, as a presence indicator. */
.docked {
  transform: scale(0.57);
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

@keyframes alarm {
  0%,
  40%,
  80% {
    stroke: var(--error);
  }
  20%,
  60%,
  100% {
    stroke: var(--ring);
  }
}
</style>
