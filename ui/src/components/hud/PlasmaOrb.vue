<script setup lang="ts">
// The plasma sphere: a soft luminous blob that boils.
//
// Explicitly not a lattice of points. A particle sphere reads as data --
// something being computed at you -- and this is the stage where E.V. is a
// presence in a dark room rather than an instrument on a desk. So: one body
// with a shimmering edge, clouds turning over inside it, grain over the lot,
// and a few bright dots going round the outside.
//
// Four passes, all clipped to a rim that is never quite a circle:
//   1. the body, a radial gradient from core blue to a lighter rim
//   2. turbulence -- a handful of soft blobs drifting on their own clocks
//   3. grain -- one noise tile, generated once, drawn twice at drifting
//      offsets so the speckle crawls rather than flickers
//   4. the rim's own light, and the dots orbiting outside it
//
// The rim is built from sines at integer multiples of the angle, which is the
// only reason it closes: a noise field sampled around a circle does not meet
// itself, and the seam is the first thing anybody sees.

import { onBeforeUnmount, onMounted, ref } from "vue";
import { useFrame } from "../../composables/useFrame";

const props = withDefaults(
  defineProps<{
    /// 0..1. The sphere breathes a little with what E.V. is saying.
    level?: number;
  }>(),
  { level: 0 },
);

const shell = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

const TAU = Math.PI * 2;

/// How much of its box the sphere fills.
///
/// Small enough that the light it throws reaches zero *inside* the canvas.
/// At 0.4 the spill was still at alpha 9 when it hit the edge of the element,
/// and a gradient cut off by a rectangle is a rectangle: there was a visible
/// pale square around the sphere, which the numbers found and the eye
/// confirmed.
const FILL = 0.3;

/// Clouds inside the body. Few and large: many and small is grain, which is
/// a separate pass.
const CLOUDS = [
  { at: 0.34, size: 0.62, pace: 0.19, phase: 0 },
  { at: 0.46, size: 0.48, pace: -0.13, phase: 2.1 },
  { at: 0.22, size: 0.7, pace: 0.09, phase: 4.4 },
  { at: 0.52, size: 0.36, pace: -0.23, phase: 1.2 },
  { at: 0.4, size: 0.44, pace: 0.16, phase: 5.6 },
];

/// A few, not a field. They sit just outside the surface and go round.
const ORBITS = Array.from({ length: 7 }, (_, i) => ({
  at: 1.1 + ((i * 7) % 5) / 22,
  pace: (i % 2 === 0 ? 1 : -1) * (0.06 + ((i * 3) % 7) / 90),
  phase: (i / 7) * TAU,
  size: 1.1 + ((i * 5) % 3) / 2.2,
}));

let grain: HTMLCanvasElement | null = null;

/// One tile, made once. Drawn twice a frame at drifting offsets, which is
/// what makes the speckle crawl instead of flicker -- regenerating it per
/// frame looks like television static and costs a hundred times as much.
function makeGrain(): HTMLCanvasElement {
  const side = 128;
  const tile = document.createElement("canvas");
  tile.width = side;
  tile.height = side;
  const ctx = tile.getContext("2d");
  if (!ctx) return tile;

  const pixels = ctx.createImageData(side, side);
  for (let i = 0; i < side * side; i += 1) {
    const value = 90 + Math.random() * 165;
    pixels.data[i * 4] = value;
    pixels.data[i * 4 + 1] = value;
    pixels.data[i * 4 + 2] = value;
    pixels.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(pixels, 0, 0);
  return tile;
}

let core = "46, 127, 232";
let rim = "125, 184, 255";

function readPalette() {
  const style = getComputedStyle(document.documentElement);
  const found = style.getPropertyValue("--plasma-core").trim();
  const edge = style.getPropertyValue("--plasma-rim").trim();
  if (found.startsWith("#")) core = hexToRgb(found);
  if (edge.startsWith("#")) rim = hexToRgb(edge);
}

function hexToRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}`;
}

/// The rim's wobble at an angle. Integer multiples only, so it closes.
function boil(angle: number, t: number): number {
  return (
    1 +
    0.022 * Math.sin(3 * angle + t * 0.7) +
    0.016 * Math.sin(5 * angle - t * 0.5) +
    0.011 * Math.sin(8 * angle + t * 0.31)
  );
}

let smooth = 0;
let dirty = true;
const still = window.matchMedia("(prefers-reduced-motion: reduce)");

function draw(now: number) {
  const box = shell.value;
  const face = canvas.value;
  const ctx = face?.getContext("2d");
  if (!box || !face || !ctx || !grain) return;
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

  const t = still.matches ? 6 : now / 1000;
  smooth += (props.level - smooth) * 0.08;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, wide, tall);
  ctx.translate(wide / 2, tall / 2);

  const r = Math.min(wide, tall) * FILL * (1 + smooth * 0.02);

  // The rim, as a path. Everything the body is made of is clipped to it, so
  // the boiling edge is the shape of the sphere rather than a line drawn on
  // top of one.
  const edge = new Path2D();
  for (let i = 0; i <= 96; i += 1) {
    const angle = (i / 96) * TAU;
    const at = r * boil(angle, t);
    const x = Math.cos(angle) * at;
    const y = Math.sin(angle) * at;
    if (i === 0) edge.moveTo(x, y);
    else edge.lineTo(x, y);
  }
  edge.closePath();

  // --- outside: the light it throws ------------------------------------
  ctx.globalCompositeOperation = "lighter";
  const spill = ctx.createRadialGradient(0, 0, r * 0.8, 0, 0, r * 1.6);
  spill.addColorStop(0, `rgba(${core}, 0.36)`);
  spill.addColorStop(0.5, `rgba(${core}, 0.1)`);
  spill.addColorStop(1, `rgba(${core}, 0)`);
  ctx.fillStyle = spill;
  ctx.beginPath();
  ctx.arc(0, 0, r * 1.6, 0, TAU);
  ctx.fill();

  ctx.save();
  ctx.clip(edge);

  // --- the body ---------------------------------------------------------
  ctx.globalCompositeOperation = "source-over";
  const body = ctx.createRadialGradient(
    -r * 0.15,
    -r * 0.2,
    r * 0.05,
    0,
    0,
    r * 1.05,
  );
  // Core at the middle, lighter rim at the edge -- the way the specification
  // states it. Inverted, it reads as a hot white centre, which is a different
  // object: a star rather than a plasma ball.
  body.addColorStop(0, `rgba(${core}, 0.97)`);
  body.addColorStop(0.55, `rgba(${core}, 0.9)`);
  body.addColorStop(0.88, `rgba(${rim}, 0.82)`);
  body.addColorStop(1, `rgba(${rim}, 0.6)`);
  ctx.fillStyle = body;
  ctx.fill(edge);

  // --- turbulence -------------------------------------------------------
  ctx.globalCompositeOperation = "lighter";
  for (const cloud of CLOUDS) {
    const angle = cloud.phase + t * cloud.pace;
    const x = Math.cos(angle) * r * cloud.at;
    const y = Math.sin(angle * 1.3) * r * cloud.at * 0.8;
    const size = r * cloud.size;
    const blob = ctx.createRadialGradient(x, y, 0, x, y, size);
    blob.addColorStop(0, `rgba(${rim}, 0.2)`);
    blob.addColorStop(0.6, `rgba(${rim}, 0.04)`);
    blob.addColorStop(1, `rgba(${rim}, 0)`);
    ctx.fillStyle = blob;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, TAU);
    ctx.fill();
  }

  // --- grain ------------------------------------------------------------
  // Two passes at different drifts and scales, so the speckle has depth and
  // no single tile edge is ever legible.
  ctx.globalCompositeOperation = "overlay";
  ctx.globalAlpha = 0.16;
  const span = r * 2.4;
  ctx.drawImage(
    grain,
    -r - ((t * 6) % span),
    -r - ((t * 4) % span),
    span,
    span,
  );
  ctx.globalAlpha = 0.1;
  ctx.drawImage(
    grain,
    -r + ((t * 3) % span) - span * 0.5,
    -r - ((t * 5) % span) + span * 0.3,
    span * 1.6,
    span * 1.6,
  );
  ctx.globalAlpha = 1;

  ctx.restore();

  // --- the dots outside -------------------------------------------------
  ctx.globalCompositeOperation = "lighter";
  for (const dot of ORBITS) {
    const angle = dot.phase + t * dot.pace * TAU * 0.2;
    const at = r * dot.at;
    const x = Math.cos(angle) * at;
    const y = Math.sin(angle) * at * 0.92;
    const halo = ctx.createRadialGradient(x, y, 0, x, y, dot.size * 5);
    halo.addColorStop(0, `rgba(255, 255, 255, 0.85)`);
    halo.addColorStop(0.25, `rgba(${rim}, 0.5)`);
    halo.addColorStop(1, `rgba(${rim}, 0)`);
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(x, y, dot.size * 5, 0, TAU);
    ctx.fill();
  }

  ctx.globalCompositeOperation = "source-over";
  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

useFrame(draw);

let watcher: ResizeObserver | null = null;

onMounted(() => {
  readPalette();
  grain = makeGrain();
  if (shell.value) {
    watcher = new ResizeObserver(() => (dirty = true));
    watcher.observe(shell.value);
  }
});

onBeforeUnmount(() => watcher?.disconnect());
</script>

<template>
  <div ref="shell" class="plasma">
    <canvas ref="canvas" aria-hidden="true" />
    <p class="wordmark">EV</p>
  </div>
</template>

<style scoped>
.plasma {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
}

canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* On the sphere, not beside it. White, geometric, letter-spaced -- the same
   wordmark the ring carries, sitting on a brighter field. */
.wordmark {
  position: relative;
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: clamp(13px, 1.6vmin, 19px);
  font-weight: 600;
  letter-spacing: 0.34em;
  text-indent: 0.34em;
  color: #fff;
  /* White type on a lit body needs something behind it, and a dark halo is
     the only thing that will not read as a second light source. */
  text-shadow:
    0 0 10px rgba(8, 24, 52, 0.75),
    0 0 26px rgba(8, 24, 52, 0.6);
}
</style>
