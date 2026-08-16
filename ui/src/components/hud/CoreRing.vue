<script setup lang="ts">
// The core: a thin white ring, the wheels turning around it, and the neon
// that arrives when E.V. is listening.
//
// White is the resting state and neon is the exception. The ring itself never
// turns blue -- awake adds a halo *around* a crisp white circle, which is what
// makes the glow read as light rather than as a recolour. An interface where
// the shape changes colour to mean something has spent the only strong signal
// it has.
//
// Canvas for the geometry, DOM for the wordmark. Sixty-odd primitives a frame
// is nothing, and text set in a real font beats text drawn into a bitmap at
// any size.

import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useFrame } from "../../composables/useFrame";
import type { Voice } from "../../stores/assistant";

const props = withDefaults(
  defineProps<{
    /// 0 idle, 1 awake. The same number the grid brightens by, so the ring and
    /// the squares cannot come up at different rates.
    lit?: number;
    voice?: Voice;
    /// 0..1, raw. Smoothed here.
    level?: number;
    /// Awake with something open on it: the core leaves the middle.
    working?: boolean;
  }>(),
  { lit: 0, voice: "idle", level: 0, working: false },
);

const shell = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

const TAU = Math.PI * 2;

/// The ring, as a fraction of the shorter side of the display.
const RADIUS = 0.16;

/// The wheels: where each sits, how long a turn takes, and how much of a
/// circle it is. At least one goes the other way, which is what stops three
/// arcs reading as one thick dashed ring.
const WHEELS = [
  { at: 1.06, seconds: 9, sweep: 110, back: false },
  { at: 1.12, seconds: 14, sweep: 64, back: true },
  { at: 0.94, seconds: 6, sweep: 88, back: false },
];

/// Sparse, small and calm -- a few dozen at most. This is the "atom orbs"
/// field from the reference, not a particle sphere.
const DOTS = 42;

interface Dot {
  angle: number;
  at: number;
  size: number;
  phase: number;
  twinkle: number;
  /// A handful drift; the rest hold still and only breathe.
  drift: number;
}

/// Fixed rather than random: the same field every time it is mounted, so the
/// display does not reshuffle its own stars on a reload.
function hash(n: number): number {
  const wave = Math.sin(n * 127.1) * 43758.5453;
  return wave - Math.floor(wave);
}

const dots: Dot[] = Array.from({ length: DOTS }, (_, i) => ({
  angle: hash(i * 1.7) * TAU,
  // Spread out to r x 2.2, denser near the ring than at the edge of the
  // field: sqrt keeps them from clumping in the middle.
  at: 0.55 + Math.sqrt(hash(i * 3.3)) * 1.65,
  size: 1 + hash(i * 5.1),
  phase: hash(i * 7.9) * TAU,
  twinkle: 0.35 + hash(i * 11.3) * 0.5,
  drift: hash(i * 13.7) < 0.2 ? (hash(i * 17.3) - 0.5) * 0.06 : 0,
}));

let smooth = 0;
let turned = 0;
let dirty = true;
const still = window.matchMedia("(prefers-reduced-motion: reduce)");

/// Neon, as canvas needs it. Read once and on demand rather than per frame.
let neon = "58, 160, 255";
let white = "238, 244, 251";

function readPalette() {
  const style = getComputedStyle(document.documentElement);
  const found = style.getPropertyValue("--neon").trim();
  if (found.startsWith("#")) neon = hexToRgb(found);
  const ink = style.getPropertyValue("--ink").trim();
  if (ink.startsWith("#")) white = hexToRgb(ink);
}

function hexToRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}`;
}

function draw(now: number, delta: number) {
  const box = shell.value;
  const face = canvas.value;
  const ctx = face?.getContext("2d");
  if (!box || !face || !ctx) return;
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
  const lit = Math.min(1, Math.max(0, props.lit));

  // Two smoothings. The level is jittery and would make the ring buzz; the
  // rotation is accumulated so a change of speed does not jump the arcs.
  smooth += (props.level - smooth) * 0.15;
  // Awake turns about twice as fast as idle.
  turned += step * (1 + lit);

  // Listening holds a steadier, brighter glow. Speaking pulses on the
  // envelope of what is being said -- scale a few percent, glow a third.
  const speaking = props.voice === "speaking";
  const listening = props.voice === "listening";
  const pulse = speaking ? smooth : 0;
  const glow = lit * (1 + (listening ? 0.25 : 0) + pulse * 0.3);

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, wide, tall);
  ctx.translate(wide / 2, tall / 2);

  const r = Math.min(wide, tall) * RADIUS * (1 + pulse * 0.03);

  // --- the halo ---------------------------------------------------------
  // Only when awake, and always behind the ring: light around a white
  // circle, never a blue circle.
  if (glow > 0.01) {
    // The peak sits *on* the ring, not outside it. Put it further out and the
    // glow reads as a blue donut around a white circle rather than as the
    // white circle giving off light.
    const halo = ctx.createRadialGradient(0, 0, r * 0.55, 0, 0, r * 1.55);
    halo.addColorStop(0, `rgba(${neon}, 0)`);
    halo.addColorStop(0.45, `rgba(${neon}, ${0.45 * glow})`);
    halo.addColorStop(0.72, `rgba(${neon}, ${0.16 * glow})`);
    halo.addColorStop(1, `rgba(${neon}, 0)`);
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(0, 0, r * 1.5, 0, TAU);
    ctx.fill();
  }

  // --- the dots ---------------------------------------------------------
  // Faint stars in the ring's neighbourhood, twinkling slowly. Drawn under
  // the linework so nothing sits on top of the ring.
  for (const dot of dots) {
    const angle = dot.angle + turned * dot.drift;
    const at = r * dot.at;
    const breath = 0.5 + 0.5 * Math.sin(t * dot.twinkle + dot.phase);
    ctx.fillStyle = `rgba(${white}, ${0.15 + breath * 0.5})`;
    ctx.beginPath();
    ctx.arc(Math.cos(angle) * at, Math.sin(angle) * at, dot.size, 0, TAU);
    ctx.fill();
  }

  // --- the crown --------------------------------------------------------
  // Awake only, and turning against the wheels: ticks and single dots on a
  // wider circle.
  if (lit > 0.01) {
    const crown = r * 1.35;
    const spin = -turned * 0.12;
    for (let i = 0; i < 12; i += 1) {
      const angle = spin + (i / 12) * TAU;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      ctx.strokeStyle = `rgba(${white}, ${0.85 * lit})`;
      ctx.lineWidth = 1;
      if (i % 3 === 0) {
        // Every third is a longer stroke; the rest are single dots.
        ctx.beginPath();
        ctx.moveTo(cos * crown, sin * crown);
        ctx.lineTo(cos * (crown + 6), sin * (crown + 6));
        ctx.stroke();
      } else {
        ctx.fillStyle = `rgba(${white}, ${0.7 * lit})`;
        ctx.beginPath();
        ctx.arc(cos * crown, sin * crown, 1.2, 0, TAU);
        ctx.fill();
      }
    }
  }

  // --- the ring ---------------------------------------------------------
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = `rgba(${white}, ${0.9 + lit * 0.1})`;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, TAU);
  ctx.stroke();

  // --- the wheels -------------------------------------------------------
  for (const wheel of WHEELS) {
    const angle = ((turned / wheel.seconds) % 1) * TAU * (wheel.back ? -1 : 1);
    const sweep = (wheel.sweep * Math.PI) / 180;
    ctx.lineWidth = wheel.at > 1.1 ? 1 : 1.5;
    ctx.strokeStyle = `rgba(${white}, ${0.7 + lit * 0.3})`;
    ctx.beginPath();
    ctx.arc(0, 0, r * wheel.at, angle, angle + sweep);
    ctx.stroke();
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

useFrame(draw);

let watcher: ResizeObserver | null = null;

onMounted(() => {
  readPalette();
  if (shell.value) {
    watcher = new ResizeObserver(() => (dirty = true));
    watcher.observe(shell.value);
  }
});

onBeforeUnmount(() => watcher?.disconnect());

/// Out to the right edge and up in size when a widget opens: the middle of
/// the display belongs to what was opened, and the core keeps turning at the
/// side of it, partly off-screen.
const drift = computed(() =>
  props.working ? "translateX(26%) scale(1.6)" : "translateX(0) scale(1)",
);
</script>

<template>
  <div ref="shell" class="core" :style="{ transform: drift }">
    <canvas ref="canvas" aria-hidden="true" />
    <p class="wordmark">EV</p>
  </div>
</template>

<style scoped>
.core {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
  /* Half a second, eased: the drift is a move, not a jump, and it is the
     only thing on screen that travels. */
  transition: transform 0.5s cubic-bezier(0.33, 1, 0.68, 1);
}

canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* Geometric, uppercase, widely tracked -- and white, always. The wordmark is
   the one piece of type on this display that never takes the neon. */
.wordmark {
  position: relative;
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: clamp(13px, 1.5vmin, 18px);
  font-weight: 600;
  letter-spacing: 0.34em;
  /* The tracking is added after the last letter too; this takes it back so
     the word sits on the centre rather than left of it. */
  text-indent: 0.34em;
  color: var(--ink);
}

@media (prefers-reduced-motion: reduce) {
  .core {
    transition: none;
  }
}
</style>
