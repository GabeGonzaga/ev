<script setup lang="ts">
// The orb. Nine hundred points on a sphere, and how loud the room is.
//
// It is the only thing on the idle screen and the only thing that moves on
// the active one, so it carries the whole impression of whether E.V. is alive
// and what it is doing. A ring would have said "loading". A sphere that
// ripples when somebody speaks says something a label cannot.
//
// Canvas, and one sprite. The glow is a radial gradient rendered once into an
// offscreen canvas at init and stamped nine hundred times a frame with
// `lighter`; `shadowBlur` per point is the same picture at a tenth of the
// frame rate, because it re-rasterises a blur for every dot. Everything else
// here -- typed arrays, a preallocated order, a single shared rAF -- exists
// so that stamping nine hundred sprites is all the work there is.

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useAppearance } from "../../stores/appearance";
import type { AssistantState } from "../../stores/assistant";
import { useFrame } from "../../composables/useFrame";

const props = withDefaults(
  defineProps<{
    /// 0..1, raw. Smoothed here rather than by whoever measured it.
    level?: number;
    state?: AssistantState;
    /// Edge length in CSS pixels. Left out, the orb fills whatever box it is
    /// given, which is what the docked badge and the idle screen both want.
    size?: number;
    /// Docked: the same particle field, smaller, inside counter-rotating
    /// rings. The badge E.V. becomes once the HUD is up.
    docked?: boolean;
    label?: string;
  }>(),
  { level: 0, state: "IDLE", label: "EV" },
);

const appearance = useAppearance();
const shell = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

/// Enough that the surface reads as a surface at any size. The cost is one
/// sprite stamp each; everything in this file is arranged around that being
/// the only cost.
const DOTS = 900;

/// How far the eye sits from the centre, in sphere radii. Near enough that
/// the front of the sphere is visibly larger than the back -- without that,
/// depth-sorting a lattice produces a disc.
const EYE = 2.6;

/// How much of the sprite is halo rather than core. The gradient's bright
/// part occupies the middle fifth, so a dot drawn at 3.4x its radius has a
/// core the right size and a glow around it.
const SPREAD = 3.4;

const boxed = computed(() =>
  props.size ? { width: `${props.size}px`, height: `${props.size}px` } : undefined,
);

// --- the lattice ---------------------------------------------------------

// Fibonacci, because latitude/longitude loops crowd the poles and crowded
// poles are the first thing an eye finds in a field of dots.
const golden = Math.PI * (3 - Math.sqrt(5));
const baseX = new Float32Array(DOTS);
const baseY = new Float32Array(DOTS);
const baseZ = new Float32Array(DOTS);
const seed = new Float32Array(DOTS);
const pace = new Float32Array(DOTS);

for (let i = 0; i < DOTS; i += 1) {
  // Jittered off the lattice, deterministically. A clean Fibonacci sphere
  // drawn with lit points shows its own spiral arms -- the eye finds the
  // construction before it finds the sphere. Half a step of scatter breaks
  // the arms and leaves the coverage even.
  const along = i + (hash(i * 3.1) - 0.5) * 0.85;
  const y = 1 - (along / (DOTS - 1)) * 2;
  const belt = Math.sqrt(Math.max(0, 1 - y * y));
  const turn = golden * i + (hash(i * 7.7) - 0.5) * 0.6;
  baseX[i] = Math.cos(turn) * belt;
  baseY[i] = y;
  baseZ[i] = Math.sin(turn) * belt;
  // Fixed rather than random: the same sphere every time it is mounted.
  seed[i] = (i * 12.9898) % 97;
  pace[i] = 0.25 + ((i * 7) % 17) / 34;
}

// Filled every frame, sorted every frame, allocated once.
const projX = new Float32Array(DOTS);
const projY = new Float32Array(DOTS);
const projD = new Float32Array(DOTS);
const projR = new Float32Array(DOTS);
const order = new Int32Array(DOTS);
for (let i = 0; i < DOTS; i += 1) order[i] = i;

/// Value noise, one dimension, deterministic. Each point walks its own line
/// through it, which is what makes the surface ripple rather than breathe:
/// a sphere where every point swells together is a balloon.
function noise(at: number, t: number): number {
  const cell = Math.floor(t);
  const into = t - cell;
  // Smoothstep, so the lattice does not show up as a kink every whole number.
  const eased = into * into * (3 - 2 * into);
  return hash(at + cell) * (1 - eased) + hash(at + cell + 1) * eased;
}

function hash(n: number): number {
  const wave = Math.sin(n * 127.1) * 43758.5453;
  return wave - Math.floor(wave);
}

// --- what each state looks like ------------------------------------------

interface Look {
  /// Multiplier on the base 0.15 rad/s.
  spin: number;
  /// How much of the audio level reaches the surface.
  amp: number;
  /// How far the per-point noise pushes points off the sphere.
  ripple: number;
  /// The whole sphere's radius. Thinking pulls it in.
  contract: number;
  /// Brightness.
  glow: number;
}

const LOOKS: Record<AssistantState, Look> = {
  // Calm, slow, barely moving: nothing is happening and the screen should
  // say so.
  IDLE: { spin: 1, amp: 0.3, ripple: 0.03, contract: 1, glow: 0.85 },
  // Scattered, briefly, on the way up.
  WAKING: { spin: 1.9, amp: 0.6, ripple: 0.1, contract: 1.07, glow: 1.25 },
  ACTIVE: { spin: 1.15, amp: 0.45, ripple: 0.04, contract: 1, glow: 0.95 },
  LISTENING: { spin: 1.45, amp: 0.75, ripple: 0.055, contract: 1.02, glow: 1.1 },
  // Pulled toward the centre and turning faster -- the shape of attention
  // rather than of speech.
  THINKING: { spin: 2.3, amp: 0.35, ripple: 0.07, contract: 0.82, glow: 0.95 },
  SPEAKING: { spin: 1.25, amp: 1, ripple: 0.05, contract: 1, glow: 1.15 },
};

// The look in force, which chases the state's rather than snapping to it:
// LISTENING arriving as a jump-cut looks like a bug in the renderer.
const look: Look = { ...LOOKS.IDLE };

// --- the sprite ----------------------------------------------------------

let sprite: HTMLCanvasElement | null = null;

function drawSprite() {
  const face = document.createElement("canvas");
  const side = 64;
  face.width = side;
  face.height = side;
  const ctx = face.getContext("2d");
  if (!ctx) return;

  const style = getComputedStyle(document.documentElement);
  const neon = style.getPropertyValue("--neon").trim() || "#3d9bff";
  const bright = style.getPropertyValue("--neon-bright").trim() || "#8fcbff";

  const half = side / 2;
  const glow = ctx.createRadialGradient(half, half, 0, half, half, half);
  // White at the very centre only: a lit point is white in the middle and
  // coloured at the edges, and doing it the other way round reads as a
  // sticker rather than as a light.
  glow.addColorStop(0, "rgba(255,255,255,1)");
  glow.addColorStop(0.12, hexTo(bright, 0.95));
  glow.addColorStop(0.28, hexTo(neon, 0.5));
  glow.addColorStop(0.6, hexTo(neon, 0.1));
  glow.addColorStop(1, hexTo(neon, 0));

  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, side, side);
  sprite = face;
}

/// `#3d9bff` at an alpha, without pulling in a colour library for it.
function hexTo(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((part) => part + part)
          .join("")
      : clean;
  const value = Number.parseInt(full, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

// --- drawing -------------------------------------------------------------

let smooth = 0;
let yaw = 0;
let dirty = true;
const still = window.matchMedia("(prefers-reduced-motion: reduce)");

function draw(now: number, delta: number) {
  const box = shell.value;
  const face = canvas.value;
  const ctx = face?.getContext("2d");
  if (!box || !face || !ctx || !sprite) return;

  // Asked not to animate: hold the sphere still and redraw only when
  // something other than time has changed.
  if (still.matches && !dirty) return;
  dirty = false;

  const dpr = window.devicePixelRatio || 1;
  const wide = box.clientWidth;
  const tall = box.clientHeight;
  if (!wide || !tall) return;

  if (face.width !== Math.round(wide * dpr) || face.height !== Math.round(tall * dpr)) {
    face.width = Math.round(wide * dpr);
    face.height = Math.round(tall * dpr);
  }

  const step = still.matches ? 0 : Math.min(delta, 50) / 1000;
  const t = now / 1000;

  // Two smoothings, both deliberate. The level is jittery and would make the
  // surface buzz; the look changes in steps and would make it jump.
  smooth += (props.level - smooth) * 0.15;
  const target = LOOKS[props.state];
  const ease = still.matches ? 1 : 0.06;
  look.spin += (target.spin - look.spin) * ease;
  look.amp += (target.amp - look.amp) * ease;
  look.ripple += (target.ripple - look.ripple) * ease;
  look.contract += (target.contract - look.contract) * ease;
  look.glow += (target.glow - look.glow) * ease;

  yaw += step * 0.15 * look.spin;
  const pitch = Math.sin(t * 0.35) * 0.22;
  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosX = Math.cos(pitch);
  const sinX = Math.sin(pitch);

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, wide, tall);
  ctx.translate(wide / 2, tall / 2);

  const radius = Math.min(wide, tall) * (props.docked ? 0.3 : 0.42);
  // The stated 0.6..2.2px is right at a badge; a sphere filling half a screen
  // needs proportionally more, or nine hundred points read as dust.
  const scale = Math.max(props.docked ? 0.55 : 0.85, Math.min(2.2, radius / 90));

  // Nine hundred additive sprites inside 110px is not a sphere, it is a white
  // disc: the field saturates long before the depth can be read. The badge
  // draws every third point, which is the same sphere at a third of the
  // density rather than a different, smaller one.
  const stride = props.docked ? 3 : 1;
  const dim = props.docked ? 0.72 : 1;

  for (let i = 0; i < DOTS; i += 1) {
    const swell =
      look.contract *
      (1 + smooth * 0.35 * look.amp + (noise(seed[i], t * pace[i]) - 0.5) * look.ripple * 2);

    const x = baseX[i] * swell;
    const y = baseY[i] * swell;
    const z = baseZ[i] * swell;

    const rx = x * cosY - z * sinY;
    const rz = x * sinY + z * cosY;
    const ry = y * cosX - rz * sinX;
    const depth = y * sinX + rz * cosX;
    const near = EYE / (EYE - depth);

    projX[i] = rx * radius * near;
    projY[i] = ry * radius * near;
    projD[i] = depth;
    projR[i] = near;
  }

  // Back to front. The sprite is additive, so the order only matters for
  // size and alpha -- but those are what carry the depth.
  order.sort((a, b) => projD[a] - projD[b]);

  ctx.globalCompositeOperation = "lighter";

  for (let n = 0; n < DOTS; n += stride) {
    const i = order[n];
    // Curved rather than linear. The back half of a sphere falls away
    // quickly; drawn linearly it stays bright enough to read as the front of
    // a second sphere, and the whole thing turns into a ball of wool.
    const depth = Math.min(1, Math.max(0, (projD[i] + 1) / 2));
    const front = depth * depth * (3 - 2 * depth);
    const size = (0.6 + front * 1.6) * scale * projR[i];
    const reach = size * SPREAD;

    ctx.globalAlpha = Math.min(1, (0.12 + front * 0.88) * look.glow * dim);
    ctx.drawImage(sprite, projX[i] - reach, projY[i] - reach, reach * 2, reach * 2);
  }

  ctx.globalAlpha = 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = "source-over";
}

useFrame(draw);

let watcher: ResizeObserver | null = null;

onMounted(() => {
  drawSprite();
  if (shell.value) {
    watcher = new ResizeObserver(() => (dirty = true));
    watcher.observe(shell.value);
  }
});

onBeforeUnmount(() => watcher?.disconnect());

// The sprite carries the palette, so it is re-rendered when the palette
// changes rather than being tinted per point.
watch(
  () => [appearance.accent, appearance.resolved],
  () => {
    drawSprite();
    dirty = true;
  },
);

watch(() => [props.state, props.size, props.docked], () => (dirty = true));
</script>

<template>
  <div ref="shell" class="orb" :class="{ docked }" :style="boxed">
    <canvas ref="canvas" aria-hidden="true" />

    <!-- Docked, the field gets a frame: two thin rings turning against each
         other. At 110px there are not enough points left to read as a sphere,
         and the rings are what say "instrument" at that size. -->
    <svg v-if="docked" class="rings" viewBox="0 0 100 100" fill="none" aria-hidden="true">
      <circle class="ring out" cx="50" cy="50" r="47" pathLength="100" />
      <circle class="ring in" cx="50" cy="50" r="40" pathLength="100" />
    </svg>

    <p class="wordmark">{{ label }}</p>

    <slot />
  </div>
</template>

<style scoped>
.orb {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  min-height: 0;
}

canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.rings {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.ring {
  stroke: var(--neon);
  stroke-width: 0.7;
  opacity: 0.55;
  transform-origin: 50% 50%;
}

/* Broken into arcs rather than closed, so the counter-rotation is visible at
   all -- a full circle turning looks like a full circle. */
.ring.out {
  stroke-dasharray: 18 6 32 44;
  animation: turn 14s linear infinite;
}

/* The rings arrive with the badge rather than appearing on it: the orb is
   still travelling when they mount, and a hard cut at that moment reads as
   two things happening instead of one. */
.rings {
  animation: arrive 0.45s ease-out both;
}

.ring.in {
  opacity: 0.35;
  stroke-dasharray: 26 10 12 52;
  animation: turn 22s linear infinite reverse;
}

/* One of the two things on this display allowed to be pure white -- and it
   has nine hundred lit points behind it, so it is given somewhere dark to
   sit or it is the least legible thing on the screen it names. */
.wordmark::before {
  content: "";
  position: absolute;
  inset: -14px -24px;
  z-index: -1;
  background: radial-gradient(closest-side, var(--bg-void) 25%, transparent 100%);
  opacity: 0.85;
}

.wordmark {
  position: relative;
  isolation: isolate;
  z-index: 1;
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.42em;
  /* The tracking is added after the last letter too; this takes it back so
     the word sits on the centre rather than left of it. */
  text-indent: 0.42em;
  color: #fff;
  text-shadow: var(--neon-glow-text);
  user-select: none;
}

@keyframes turn {
  to {
    transform: rotate(360deg);
  }
}

@keyframes arrive {
  from {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ring {
    animation: none;
  }

  .rings {
    animation-duration: 0.01ms;
  }
}
</style>
