<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { State } from "../stores/session";
import { useAppearance } from "../stores/appearance";

const props = defineProps<{ state: State; ambient?: boolean }>();
const appearance = useAppearance();
const canvas = ref<HTMLCanvasElement | null>(null);

/// The sphere is a cloud of dots spread evenly over its surface (a Fibonacci
/// lattice), turned live so the near side reads bright and large and the far
/// side dim and small. That depth is the whole trick: without it, a rotating
/// scatter of dots is just a flickering disc.
const N = 560;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
type Dot = { x: number; y: number; z: number; ph: number };
const DOTS: Dot[] = Array.from({ length: N }, (_, i) => {
  const y = 1 - (i / (N - 1)) * 2;
  const r = Math.sqrt(1 - y * y);
  const th = GOLDEN * i;
  return { x: Math.cos(th) * r, y, z: Math.sin(th) * r, ph: ((i * 41) % 100) / 100 };
});

/// A few brighter points on tilted circular orbits -- the atom read. Each
/// dims behind the sphere and brightens as it swings to the front.
type Orbit = { tiltX: number; tiltZ: number; speed: number; phase: number };
const ELECTRONS: Orbit[] = [
  { tiltX: 1.15, tiltZ: 0.2, speed: 1.05, phase: 0.0 },
  { tiltX: 0.35, tiltZ: 1.3, speed: -0.8, phase: 2.1 },
  { tiltX: 1.5, tiltZ: 1.0, speed: 0.62, phase: 4.0 },
];

/// Eight clusters of three short dashes: the quiet HUD crown around the orb,
/// the one piece of the old ring that stays.
const GROUPS = 8;
const PER = 3;

type Rgb = [number, number, number];

/// Read the accent from the stylesheet so the sphere follows the chosen hue
/// (cyan, vaporeon, ...) and the theme, rather than hard-coding one blue.
let accent: Rgb = [30, 144, 255];
let ringTop: Rgb = [120, 210, 255];
let live: Rgb = [255, 77, 77];
// Dark is what it was drawn for; light is the same instrument in daylight,
// where an additive glow on a white page shows nothing and the dots have to
// be painted solid instead.
let isDark = true;

function parseTriple(value: string, fallback: Rgb): Rgb {
  const parts = value.split(",").map((s) => parseFloat(s.trim()));
  return parts.length === 3 && parts.every((n) => !Number.isNaN(n))
    ? (parts as Rgb)
    : fallback;
}

function parseHex(value: string, fallback: Rgb): Rgb {
  const hex = value.trim().replace("#", "");
  if (hex.length !== 6) return fallback;
  const n = parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  accent = parseTriple(cs.getPropertyValue("--accent"), accent);
  ringTop = parseTriple(cs.getPropertyValue("--ring-top"), ringTop);
  live = parseHex(cs.getPropertyValue("--live"), live);
  // The theme is an attribute on <html>, resolved from the system by the
  // appearance store. Anything but an explicit "light" is treated as dark.
  isDark = document.documentElement.dataset.theme !== "light";
}

const rgba = (c: Rgb, a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const mix = (a: Rgb, b: Rgb, k: number): Rgb => [
  a[0] + (b[0] - a[0]) * k,
  a[1] + (b[1] - a[1]) * k,
  a[2] + (b[2] - a[2]) * k,
];

/// How the sphere is coloured and composited, per theme and per state.
///
/// `deep` is the far side, `near` the side facing you; the dots run between
/// them by depth. In the dark the two are painted additively and run bright,
/// the way lit gas does; in daylight they are painted solid and run from a
/// rich blue at the front to a pale one at the back, because additive light on
/// a white page is invisible. Listening turns the whole thing red -- the one
/// state that should read from across the room, as the old ring did.
type Scheme = { deep: Rgb; near: Rgb; glow: Rgb; comp: GlobalCompositeOperation };
function scheme(): Scheme {
  if (props.state === "listening") {
    return isDark
      ? { deep: mix(live, [40, 0, 0], 0.2), near: mix(live, [255, 255, 255], 0.5), glow: live, comp: "lighter" }
      : { deep: mix(live, [255, 255, 255], 0.55), near: live, glow: live, comp: "source-over" };
  }
  return isDark
    ? { deep: accent, near: mix(ringTop, [255, 255, 255], 0.35), glow: accent, comp: "lighter" }
    : { deep: mix(accent, [255, 255, 255], 0.55), near: mix(accent, [8, 40, 96], 0.15), glow: accent, comp: "source-over" };
}

/// Idle turns slowly; thinking and listening turn faster, because the sphere
/// is what says "it is doing something" from across the room. Same intent as
/// the old ring's pace, expressed as an angular rate.
function rate(): number {
  const pace = props.state === "idle" ? 1 : props.state === "speaking" ? 0.6 : 0.34;
  return 0.24 / pace;
}

let ctx: CanvasRenderingContext2D | null = null;
let raf = 0;
let ro: ResizeObserver | null = null;
let W = 0;
let H = 0;
let cx = 0;
let cy = 0;
let R = 0;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

// Angles are accumulated rather than derived from the clock, so a change of
// state (and therefore of rate) speeds the turn up smoothly instead of
// jumping the sphere to a new angle.
let yaw = 0.6;
let orbit = 0;
let last = 0;
const TILT = 0.42;

function resize() {
  const el = canvas.value;
  if (!el) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  W = el.clientWidth;
  H = el.clientHeight;
  el.width = Math.round(W * dpr);
  el.height = Math.round(H * dpr);
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  cx = W / 2;
  cy = H / 2;
  R = Math.min(W, H) * 0.32;
}

/// One point of an electron's orbit: a unit circle tilted into its own plane,
/// then turned by the shared yaw so the whole atom moves together.
function orbitPoint(a: number, e: Orbit, cosY: number, sinY: number) {
  let x = Math.cos(a);
  let y = 0;
  let z = Math.sin(a);
  const y1 = y * Math.cos(e.tiltX) - z * Math.sin(e.tiltX);
  const z1 = y * Math.sin(e.tiltX) + z * Math.cos(e.tiltX);
  y = y1;
  z = z1;
  const x1 = x * Math.cos(e.tiltZ) - y * Math.sin(e.tiltZ);
  const y2 = x * Math.sin(e.tiltZ) + y * Math.cos(e.tiltZ);
  x = x1;
  y = y2;
  return { x: x * cosY + z * sinY, y, z: -x * sinY + z * cosY };
}

function draw(now: number) {
  if (!ctx) return;
  const dt = last ? Math.min((now - last) / 1000, 0.05) : 0;
  last = now;
  if (!reduce) {
    yaw += dt * rate();
    orbit += dt;
  }
  const t = now / 1000;
  const { deep, near, glow, comp } = scheme();
  const breathe = reduce ? 0.9 : 0.78 + 0.22 * (0.5 + 0.5 * Math.sin(t * 1.7));
  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosT = Math.cos(TILT);
  const sinT = Math.sin(TILT);

  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.globalCompositeOperation = comp;

  // A soft halo the sphere sits inside. Quieter in daylight, where it is a
  // tint on white rather than light in the dark.
  const haloA = isDark ? 0.16 : 0.08;
  const halo = ctx.createRadialGradient(cx, cy, R * 0.15, cx, cy, R * 1.55);
  halo.addColorStop(0, rgba(glow, haloA * breathe));
  halo.addColorStop(0.55, rgba(glow, haloA * 0.4 * breathe));
  halo.addColorStop(1, rgba(glow, 0));
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, W, H);

  // Faint full orbit paths, under the dots.
  for (const e of ELECTRONS) {
    ctx.strokeStyle = rgba(near, 0.1);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let s = 0; s <= 64; s++) {
      const p = orbitPoint((s / 64) * Math.PI * 2, e, cosY, sinY);
      const px = cx + p.x * R * 1.16;
      const py = cy + p.y * R * 1.16;
      s === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  // The sphere of dots.
  for (const d of DOTS) {
    const y1 = d.y * cosT - d.z * sinT;
    const z1 = d.y * sinT + d.z * cosT;
    const x2 = d.x * cosY + z1 * sinY;
    const z2 = -d.x * sinY + z1 * cosY;
    const dn = (z2 + 1) / 2; // 0 far .. 1 near
    const tw = 0.6 + 0.4 * Math.sin(t * 1.8 + d.ph * 6.28);
    const a = isDark
      ? (0.1 + 0.72 * dn * dn) * tw * breathe
      : (0.14 + 0.7 * dn * dn) * (0.7 + 0.3 * tw);
    const size = (0.5 + 1.7 * dn) * (0.85 + 0.15 * tw);
    ctx.fillStyle = rgba(mix(deep, near, dn), a);
    ctx.beginPath();
    ctx.arc(cx + x2 * R, cy + y1 * R, size, 0, Math.PI * 2);
    ctx.fill();
  }

  // The electrons: front half of each orbit brighter, then the glowing dot.
  for (const e of ELECTRONS) {
    ctx.strokeStyle = rgba(near, 0.14);
    ctx.lineWidth = 1;
    ctx.beginPath();
    let started = false;
    for (let s = 0; s <= 64; s++) {
      const p = orbitPoint((s / 64) * Math.PI * 2, e, cosY, sinY);
      if (p.z < 0) {
        started = false;
        continue;
      }
      const px = cx + p.x * R * 1.16;
      const py = cy + p.y * R * 1.16;
      started ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      started = true;
    }
    ctx.stroke();

    const p = orbitPoint(orbit * e.speed + e.phase, e, cosY, sinY);
    const dn = (p.z + 1) / 2;
    ctx.shadowColor = rgba(glow, 0.95);
    ctx.shadowBlur = 10 + 8 * dn;
    // In the dark the near electron flares to white; in daylight that would
    // vanish, so it stays the accent, only stronger toward the front.
    const spark = isDark ? mix(deep, [220, 240, 255], dn) : mix(deep, near, dn);
    ctx.fillStyle = rgba(spark, 0.55 + 0.45 * dn);
    ctx.beginPath();
    ctx.arc(cx + p.x * R * 1.16, cy + p.y * R * 1.16, 1.6 + 1.8 * dn, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }
  ctx.restore();

  // The quiet HUD crown: a faint outer circle and grouped ticks, turning the
  // other way, very slowly.
  ctx.lineWidth = 0.75;
  ctx.strokeStyle = rgba(accent, 0.14);
  ctx.beginPath();
  ctx.arc(cx, cy, R * 1.42, 0, Math.PI * 2);
  ctx.stroke();

  const crown = reduce ? 0 : -t * 0.06;
  const tickR = R * 1.44;
  for (let g = 0; g < GROUPS; g++) {
    const base = (g / GROUPS) * Math.PI * 2 + crown;
    for (let k = 0; k < PER; k++) {
      const ang = base + (k - 1) * 0.045;
      const long = k === 1;
      const r0 = tickR + (long ? 3 : 6);
      const r1 = tickR + 14;
      ctx.strokeStyle = rgba(accent, long ? 0.5 : 0.28);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0);
      ctx.lineTo(cx + Math.cos(ang) * r1, cy + Math.sin(ang) * r1);
      ctx.stroke();
    }
  }

  raf = requestAnimationFrame(draw);
}

onMounted(() => {
  const el = canvas.value;
  if (!el) return;
  ctx = el.getContext("2d");
  readPalette();
  resize();
  ro = new ResizeObserver(resize);
  ro.observe(el);
  raf = requestAnimationFrame(draw);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  ro?.disconnect();
});

// The accent and the theme both live as attributes on <html>; when either
// changes, re-read the colours the sphere is drawn in.
watch(
  () => [appearance.accent, appearance.resolved],
  () => readPalette(),
);
</script>

<template>
  <div class="core" :class="[state, { ambient }]">
    <div class="orb">
      <canvas ref="canvas" aria-hidden="true" />
      <div class="middle">
        <!-- Two letters and two periods, spaced as four beats rather than as
             a word with punctuation in it. -->
        <p class="wordmark" aria-label="E.V.">
          <span>E</span><span>.</span><span>V</span><span>.</span>
        </p>
        <slot />
      </div>
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

.orb {
  position: relative;
  width: min(320px, 92%);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
}

/* Alone on the screen, the orb can afford to be larger -- but only a little:
   it stays the thing you look at. */
.core.ambient .orb {
  width: min(440px, 62vmin);
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
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  max-width: 60%;
}

.wordmark {
  display: flex;
  /* The gap is the rhythm: a period is narrower than a letter. */
  gap: 0.14em;
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: 21px;
  font-weight: 500;
  letter-spacing: 0.12em;
  /* Adapts with the theme: near-white on the dark screen, ink in daylight. */
  color: var(--text);
  text-shadow: 0 0 22px rgba(var(--accent), 0.55), 0 0 4px rgba(var(--accent-lit), 0.35);
}

.core.ambient .wordmark {
  font-size: 24px;
}
</style>
