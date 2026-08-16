<script setup lang="ts">
// The waiting screen: a sphere of neon dots, and E.V.'s name in the middle
// of it.
//
// This is what is on the display while E.V. is waiting to be called, which is
// most of its life. A ring says "working"; a sphere that drifts says nothing
// at all, which is the correct thing to say when nothing is happening.
//
// Canvas rather than SVG: three hundred elements the browser has to lay out,
// style and composite sixty times a second is a different proposition from
// three hundred arcs drawn into a bitmap. Nothing here is interactive, so
// none of what the DOM would buy is worth paying for.

import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useAppearance } from "../stores/appearance";

const props = defineProps<{ live?: boolean }>();

const appearance = useAppearance();
const shell = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

const TAU = Math.PI * 2;

/// How many dots the sphere is made of. Enough that the surface reads as a
/// surface rather than as a constellation; few enough to draw sixty times a
/// second without the fans coming on, which matters for a screen that is
/// meant to be left alone.
const DOTS = 430;

/// Three, tilted apart, the way an atom is drawn rather than the way one is.
const SHELLS = 3;

/// How far the eye is from the centre, in sphere radii. Small enough that the
/// near face is visibly larger than the far one -- without that it is a disc
/// of dots, not a sphere.
const EYE = 2.7;

interface Dot {
  x: number;
  y: number;
  z: number;
  /// Where in its own breath this one starts, and how quickly it takes it.
  /// Fixed and uneven rather than random: the same on every mount, so the
  /// sphere does not reshuffle itself each time the screen is opened.
  phase: number;
  pace: number;
  /// How fast this one slides around the sphere on its own, on top of the
  /// turn the whole thing takes. Uneven, so the lattice shears slowly and
  /// the surface reads as something moving rather than something rotating.
  drift: number;
}

/// Evenly over a sphere, by the Fibonacci lattice. Latitude and longitude
/// loops crowd the poles, and crowded poles are exactly what the eye finds.
const dots: Dot[] = Array.from({ length: DOTS }, (_, index) => {
  const y = 1 - (index / (DOTS - 1)) * 2;
  const belt = Math.sqrt(Math.max(0, 1 - y * y));
  const turn = Math.PI * (3 - Math.sqrt(5)) * index;

  return {
    x: Math.cos(turn) * belt,
    y,
    z: Math.sin(turn) * belt,
    phase: (((index * 37) % 61) / 61) * TAU,
    pace: 0.5 + ((index * 17) % 13) / 20,
    drift: (((index * 23) % 17) / 17 - 0.5) * 0.13,
  };
});

/// The shells, as a tilt each, plus where their travelling dot is.
const shells = Array.from({ length: SHELLS }, (_, index) => ({
  tilt: (index * Math.PI) / SHELLS,
  lean: 0.5 + index * 0.42,
  pace: 0.22 + index * 0.07,
}));

/// The accent, as the numbers canvas needs. The stylesheet holds it as
/// `34, 211, 238` so that CSS can put an alpha on it; this reads the same
/// string rather than keeping a second copy of the palette.
let glow = "120, 200, 255";
let bright = "225, 245, 255";

function readPalette() {
  const style = getComputedStyle(document.documentElement);
  glow = style.getPropertyValue("--accent").trim() || glow;
  bright = style.getPropertyValue("--ring-top").trim() || bright;
}

let frame = 0;
let started = 0;
const still = window.matchMedia("(prefers-reduced-motion: reduce)");

function draw(now: number) {
  const face = canvas.value;
  const box = shell.value;
  const ctx = face?.getContext("2d");
  if (!face || !box || !ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const wide = box.clientWidth;
  const tall = box.clientHeight;
  if (face.width !== Math.round(wide * dpr) || face.height !== Math.round(tall * dpr)) {
    face.width = Math.round(wide * dpr);
    face.height = Math.round(tall * dpr);
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, wide, tall);
  ctx.translate(wide / 2, tall / 2);

  // Big enough to be the screen, small enough to leave the wordmark room.
  const radius = Math.min(wide, tall) * 0.34;
  const seconds = (now - started) / 1000;

  // One slow turn, and a lean that never quite repeats, so the sphere never
  // settles into looking like a loop.
  const yaw = seconds * 0.17;
  const pitch = Math.sin(seconds * 0.11) * 0.34;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cx = Math.cos(pitch);
  const sx = Math.sin(pitch);

  const lift = props.live ? 1.25 : 1;

  function project(x: number, y: number, z: number) {
    const rx = x * cy - z * sy;
    const rz = x * sy + z * cy;
    const ry = y * cx - rz * sx;
    const depth = y * sx + rz * cx;
    const near = EYE / (EYE - depth);
    return { x: rx * radius * near, y: ry * radius * near, near, depth };
  }

  // Additive, because that is what neon does: two dots that overlap are
  // brighter than either, and where the surface is dense it goes to white.
  ctx.globalCompositeOperation = "lighter";

  // The shells first: they belong behind the surface they orbit.
  for (const shell of shells) {
    const lean = Math.cos(shell.lean);
    const rise = Math.sin(shell.lean);

    ctx.beginPath();
    for (let step = 0; step <= 72; step += 1) {
      const angle = (step / 72) * TAU;
      const px = Math.cos(angle) * 1.2;
      const flat = Math.sin(angle) * 1.2;
      const spot = project(
        px * Math.cos(shell.tilt) - flat * rise * Math.sin(shell.tilt),
        flat * lean,
        px * Math.sin(shell.tilt) + flat * rise * Math.cos(shell.tilt),
      );
      if (step === 0) ctx.moveTo(spot.x, spot.y);
      else ctx.lineTo(spot.x, spot.y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${glow}, ${0.2 * lift})`;
    ctx.lineWidth = 1;
    ctx.stroke();

    // And the one dot going round it, which is the whole atom cue.
    const angle = seconds * shell.pace * TAU;
    const px = Math.cos(angle) * 1.2;
    const flat = Math.sin(angle) * 1.2;
    const spot = project(
      px * Math.cos(shell.tilt) - flat * rise * Math.sin(shell.tilt),
      flat * lean,
      px * Math.sin(shell.tilt) + flat * rise * Math.cos(shell.tilt),
    );
    const front = (spot.depth + 1.4) / 2.8;
    ctx.fillStyle = `rgba(${bright}, ${(0.35 + front * 0.6) * lift})`;
    ctx.beginPath();
    ctx.arc(spot.x, spot.y, (1.1 + front * 1.7) * spot.near, 0, TAU);
    ctx.fill();
  }

  // Back to front, so the near face draws over the far one and the additive
  // pass reads as depth rather than as a flat wash.
  const placed = dots
    .map((dot) => {
      // Each breathes a little in and out of the surface, and slides a little
      // around it, both on its own clock. Together they read as a sphere that
      // is alive rather than one that is spinning.
      const swell = 1 + Math.sin(seconds * dot.pace + dot.phase) * 0.05;
      const slide = seconds * dot.drift;
      const cs = Math.cos(slide);
      const ss = Math.sin(slide);
      return project(
        (dot.x * cs - dot.z * ss) * swell,
        dot.y * swell,
        (dot.x * ss + dot.z * cs) * swell,
      );
    })
    .sort((a, b) => a.depth - b.depth);

  for (const spot of placed) {
    // Curved rather than linear: the far half of a sphere should fall away
    // quickly, or the whole thing reads as a disc of evenly bright dots.
    const front = Math.pow((spot.depth + 1) / 2, 1.7);
    const size = (0.35 + front * 1.9) * spot.near;

    ctx.fillStyle = `rgba(${glow}, ${(0.04 + front * 0.26) * lift})`;
    ctx.beginPath();
    ctx.arc(spot.x, spot.y, size * 3.4, 0, TAU);
    ctx.fill();

    ctx.fillStyle = `rgba(${bright}, ${(0.1 + front * 0.85) * lift})`;
    ctx.beginPath();
    ctx.arc(spot.x, spot.y, size, 0, TAU);
    ctx.fill();
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = "source-over";
}

function run(now: number) {
  draw(now);
  frame = requestAnimationFrame(run);
}

function start() {
  cancelAnimationFrame(frame);
  // Asked not to animate: draw it once, and it is a still photograph of the
  // same sphere rather than a different screen.
  if (still.matches) return void draw(started + 2000);
  frame = requestAnimationFrame(run);
}

/// A tab in the background is not being looked at, and a sphere nobody can
/// see is a laptop running warm for no reason.
function whenSeen() {
  if (document.hidden) cancelAnimationFrame(frame);
  else start();
}

onMounted(() => {
  readPalette();
  started = performance.now();
  start();
  window.addEventListener("resize", start);
  document.addEventListener("visibilitychange", whenSeen);
  still.addEventListener("change", start);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(frame);
  window.removeEventListener("resize", start);
  document.removeEventListener("visibilitychange", whenSeen);
  still.removeEventListener("change", start);
});

// The palette is CSS, and CSS is where it changes. Re-read it when it does
// rather than every frame.
watch(
  () => [appearance.accent, appearance.resolved],
  () => readPalette(),
);
</script>

<template>
  <div ref="shell" class="orb">
    <canvas ref="canvas" aria-hidden="true" />

    <div class="middle">
      <!-- Two letters and two periods, spaced as four beats rather than as
           words with punctuation in them. -->
      <p class="wordmark" aria-label="E.V.">
        <span>E</span><span>.</span><span>V</span><span>.</span>
      </p>
      <slot />
    </div>
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

.middle {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
  max-width: 46%;
  z-index: 1;
}

/* The name has three hundred lit dots behind it. Without somewhere dark to
   sit, it is the least legible thing on a screen it is the subject of. */
.middle::before {
  content: "";
  position: absolute;
  inset: -40px -84px;
  z-index: -1;
  background: radial-gradient(closest-side, var(--page) 35%, transparent 100%);
  opacity: 0.96;
}

.wordmark {
  display: flex;
  /* The gap is the rhythm: a period is narrower than a letter, so letter
     spacing alone would leave the dots hanging closer to what precedes them. */
  gap: 0.2em;
  margin: 0;
  font-family: var(--display-font);
  font-size: 38px;
  font-weight: 300;
  letter-spacing: 0.16em;
  color: #fff;
  text-shadow:
    0 0 8px rgba(var(--ring-top), 0.95),
    0 0 34px rgba(var(--accent), 0.85);
}
</style>
