<script setup lang="ts">
// The home sphere: a shell of points with the name inside it.
//
// This is the screen E.V. spends its life on, so it is the one that has to be
// worth looking at while nothing is happening. A shell rather than a ring,
// because a ring is an instrument and this stage is not being read from -- it
// is being waited with.
//
// The points sit on a Fibonacci lattice: `y` walks the poles, the radius at
// each `y` is what is left of the unit sphere there, and the angle advances
// by the golden angle so no two turns land on each other. That is the whole
// distribution, and it is the reason the shell has no seam and no crowded
// pole.
//
// Drawn as one sprite, many times. A radial gradient rendered once into an
// offscreen canvas and blitted per point costs a fraction of what a thousand
// `arc()` fills cost, and additive blending does the rest: where points
// overlap the light builds, which is what makes a shell of dots read as a
// body rather than as a scatter. Additive is also commutative, so nothing
// here needs depth sorting -- the far side and the near side can be drawn in
// any order and land the same.
//
// WebGL would carry ten times the points. It would also carry three hundred
// kilobytes and a second rendering model into a display whose every other
// surface is canvas 2D, for a sphere that reads at this size with fifteen
// hundred. The dependency is the part that does not come back out.

import { onMounted, ref } from "vue";
import { useFrame } from "../../composables/useFrame";

const props = withDefaults(
  defineProps<{
    /// 0..1, how loud E.V. is. The shell breathes with it.
    level?: number;
    /// 0..1, how much of the shell is on screen. The sweep dissolves this
    /// into the ring rather than cutting between them.
    shown?: number;
    /// How many points. Fifteen hundred is the shell reading as solid at the
    /// size it is drawn; more is invisible and costs frames.
    points?: number;
  }>(),
  { level: 0, shown: 1, points: 1500 },
);

const shell = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

const TAU = Math.PI * 2;

/// The golden angle. Consecutive points differ by an irrational fraction of a
/// turn, which is the only reason they never line up into spokes.
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

/// A fixed lean, so the lattice reads as a sphere turning rather than as a
/// disc spinning. Without it the poles sit dead centre and the illusion goes.
const TILT = 0.42;

/// How much of the box the shell fills, leaving room for the light it throws.
///
/// Small: the reference is a compact body with a lot of dark around it, and a
/// shell that fills the screen stops being an object and becomes a texture.
const FILL = 0.19;

/// Where a point is on the unit sphere, and where the cursor has pushed it.
interface Point {
  x: number;
  y: number;
  z: number;
  /// Its own clock, so the shell shimmers instead of pulsing as one.
  phase: number;
  /// Its own brightness, and its own distance from the middle. A lattice
  /// drawn exactly is a lattice you can see the rows of -- the eye finds the
  /// spiral before it finds the sphere. Scattering both breaks the rows
  /// without touching the distribution that made the shell even.
  lit: number;
  at: number;
  /// Displacement, in unit-sphere space. Decays back to nothing.
  dx: number;
  dy: number;
  dz: number;
}

let points: Point[] = [];

function lattice(count: number): Point[] {
  return Array.from({ length: count }, (_, i) => {
    // Deterministic scatter rather than Math.random: the shell is the same
    // every launch, which is what makes it a thing rather than a shuffle.
    const noise = (seed: number) => (Math.sin(i * seed) + 1) / 2;
    const y = 1 - (i / (count - 1)) * 2 + (noise(12.9898) - 0.5) * 0.012;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN * i + (noise(78.233) - 0.5) * 0.09;
    return {
      x: Math.cos(theta) * ring,
      y,
      z: Math.sin(theta) * ring,
      phase: ((i * 37) % 100) / 100,
      lit: 0.45 + noise(43.7585) * 0.8,
      at: 0.97 + noise(93.9898) * 0.06,
      dx: 0,
      dy: 0,
      dz: 0,
    };
  });
}

/// What the cursor does, and how the shell forgets it.
///
/// Taken from the reference: a friction that eats most of the push and a
/// return force that walks the rest home. Two decays rather than one, because
/// friction alone leaves a permanent dent and a spring alone oscillates.
const FRICTION = 0.94;
const RETURN = 0.015;
const REACH = 90;
const PUSH = 0.9;

/// Where the pointer is, in canvas pixels, or null when it is elsewhere.
let cursor: { x: number; y: number } | null = null;

type Rgb = [number, number, number];

let neon: Rgb = [63, 165, 246];
let ice: Rgb = [196, 222, 243];

function readPalette() {
  const style = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: Rgb): Rgb => {
    const found = style.getPropertyValue(name).trim();
    return found.startsWith("#") ? hexToRgb(found) : fallback;
  };
  neon = read("--neon", neon);
  ice = read("--ring-ice", ice);
}

function hexToRgb(hex: string): Rgb {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

/// One point, rendered once.
///
/// A radial gradient with a hard white middle and a coloured falloff: blitted
/// additively, the middles stack into the bright grain and the falloffs into
/// the body's glow. Rebuilt only when the palette changes.
const SPRITE = 32;
let sprite: HTMLCanvasElement | null = null;

function drawSprite() {
  const face = document.createElement("canvas");
  face.width = SPRITE;
  face.height = SPRITE;
  const ctx = face.getContext("2d");
  if (!ctx) return;

  const half = SPRITE / 2;
  const glow = ctx.createRadialGradient(half, half, 0, half, half, half);
  glow.addColorStop(0, `rgba(${ice[0]}, ${ice[1]}, ${ice[2]}, 1)`);
  glow.addColorStop(0.18, `rgba(${ice[0]}, ${ice[1]}, ${ice[2]}, 0.85)`);
  glow.addColorStop(0.45, `rgba(${neon[0]}, ${neon[1]}, ${neon[2]}, 0.4)`);
  glow.addColorStop(1, `rgba(${neon[0]}, ${neon[1]}, ${neon[2]}, 0)`);
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(half, half, half, 0, TAU);
  ctx.fill();

  sprite = face;
}

let yaw = 0.6;
let smooth = 0;
const still = window.matchMedia("(prefers-reduced-motion: reduce)");

function draw(now: number, delta: number) {
  const box = shell.value;
  const face = canvas.value;
  const ctx = face?.getContext("2d");
  if (!box || !face || !ctx || !sprite) return;

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

  // The level is smoothed here rather than in the store: the store is written
  // to sixty times a second by the meter, and a shell that followed it
  // exactly would jitter rather than breathe.
  smooth += (props.level - smooth) * 0.12;
  const loud = Math.min(1, Math.max(0, smooth));

  yaw += step * 0.16;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, wide, tall);

  const cx = wide / 2;
  const cy = tall / 2;
  // Breathing, and the swell of a loud line. Small numbers on purpose: a
  // shell that visibly inflates reads as a balloon.
  const breathe = still.matches ? 1 : 1 + 0.012 * Math.sin(t * 1.1);
  const radius = Math.min(wide, tall) * FILL * breathe * (1 + loud * 0.05);

  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosT = Math.cos(TILT);
  const sinT = Math.sin(TILT);

  ctx.globalCompositeOperation = "lighter";

  // The body, under the grain. Without it the shell is a cloud of dust: the
  // reference reads as a lit sphere with speckle *on* it, and that light has
  // to come from somewhere the points are not.
  // Held close to the shell. Run out to half again the radius and it stops
  // being a body and becomes weather -- the reference's light stops at the
  // edge it belongs to.
  const body = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 1.12);
  const lift = 0.3 + loud * 0.14;
  body.addColorStop(0, `rgba(${neon[0]}, ${neon[1]}, ${neon[2]}, ${lift})`);
  body.addColorStop(0.7, `rgba(${neon[0]}, ${neon[1]}, ${neon[2]}, ${lift * 0.62})`);
  body.addColorStop(1, `rgba(${neon[0]}, ${neon[1]}, ${neon[2]}, 0)`);
  ctx.globalAlpha = props.shown;
  ctx.fillStyle = body;
  ctx.fillRect(0, 0, wide, tall);

  for (const point of points) {
    // The push the cursor gave it, walking home. Both decays run whether or
    // not the cursor is still there, so a shell nobody is touching settles.
    if (step > 0) {
      const decay = Math.pow(FRICTION, step * 60) * (1 - RETURN);
      point.dx *= decay;
      point.dy *= decay;
      point.dz *= decay;
    }

    const px = point.x + point.dx;
    const py = point.y + point.dy;
    const pz = point.z + point.dz;

    // Yaw first, then the lean: the whole lattice turns together, and the
    // lean is the camera's, not the sphere's.
    const rx = px * cosY + pz * sinY;
    const rz = -px * sinY + pz * cosY;
    const ry = py * cosT - rz * sinT;
    const depth = py * sinT + rz * cosT;

    const screenX = cx + rx * radius * point.at;
    const screenY = cy + ry * radius * point.at;

    // 0 at the back, 1 at the front. Everything the eye reads as depth comes
    // from this one number: size, brightness, and how much the cursor can
    // reach it.
    const near = (depth + 1) / 2;

    if (cursor && near > 0.5) {
      // Only the face turned towards you moves. The far side is behind the
      // body and pushing it would look like the shell leaking.
      const toX = screenX - cursor.x;
      const toY = screenY - cursor.y;
      const away = Math.hypot(toX, toY);
      if (away < REACH && away > 0.001) {
        const force = ((REACH - away) / REACH) * PUSH * 0.01;
        // Pushed in screen space, stored in lattice space: the shell keeps
        // turning under the dent rather than carrying it around.
        const angle = Math.atan2(toY, toX);
        point.dx += Math.cos(angle) * force * cosY;
        point.dz += -Math.cos(angle) * force * sinY;
        point.dy += Math.sin(angle) * force * cosT;
      }
    }

    const twinkle = 0.72 + 0.28 * Math.sin(t * 1.6 + point.phase * TAU);
    // Size keeps the square: it is the depth cue, and the eye reads it as
    // distance. Brightness does not -- on a real shell the points pile up at
    // the silhouette, so a limb crushed to nothing reads as a disc with a
    // soft edge rather than as a sphere.
    const size = (0.7 + 2.1 * near * near) * (0.85 + 0.15 * twinkle);
    ctx.globalAlpha =
      Math.min(
        1,
        (0.22 + 0.78 * near) * point.lit * twinkle * (0.9 + loud * 0.3),
      ) * props.shown;

    ctx.drawImage(sprite, screenX - size, screenY - size, size * 2, size * 2);
  }

  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
}

function follow(event: PointerEvent) {
  const box = shell.value;
  if (!box) return;
  const rect = box.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  cursor =
    x >= 0 && x <= rect.width && y >= 0 && y <= rect.height ? { x, y } : null;
}

function leave() {
  cursor = null;
}

onMounted(() => {
  readPalette();
  drawSprite();
  points = lattice(Math.max(64, props.points));
});

useFrame(draw);
</script>

<template>
  <div
    ref="shell"
    class="sphere"
    :style="{ opacity: shown }"
    @pointermove="follow"
    @pointerleave="leave"
  >
    <canvas ref="canvas" aria-hidden="true" />
    <!-- DOM, not canvas. The wordmark is type, and type drawn into a canvas
         is type that does not hint, does not subpixel and does not survive a
         change of scale. -->
    <p class="wordmark">EV</p>
  </div>
</template>

<style scoped>
.sphere {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: auto;
}

canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* Geometric, uppercase, widely tracked, and white -- the same wordmark the
   ring wears, so waking changes the sphere around the name rather than the
   name. */
.wordmark {
  position: relative;
  margin: 0;
  /* Identical to the ring's, down to the tracking: the two cross-fade in
     place, so waking changes the geometry around the name and leaves the
     name standing still. A different size here would make the swap a pop. */
  font-family: var(--wordmark-font);
  font-size: clamp(13px, 1.5vmin, 18px);
  font-weight: 600;
  letter-spacing: 0.34em;
  text-indent: 0.34em;
  color: var(--ink);
  user-select: none;
}
</style>
