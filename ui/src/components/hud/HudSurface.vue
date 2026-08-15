<script setup lang="ts">
// The display: one screen, two faces, and the 900ms between them.
//
// IDLE is a clock and an orb on a dark field. ACTIVE is the instrument. They
// are the same surface rather than two pages, because the transition between
// them is the thing worth building -- a router would make it a navigation,
// and a navigation cannot be run backwards in 500ms.
//
// Everything in that transition is derived from one number. `progress` runs
// 0 to 1 on the way up and back down on the way out; the beam's height, the
// grid's mask, the chrome's mask, the orb's journey to the corner and each
// panel's arrival are all functions of it. Nothing here is a CSS animation
// with its own clock, because five clocks agreeing for 900ms is luck.
//
// Fixed to the viewport and never scrolls. A HUD that scrolls is a document.

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import TheClock from "../TheClock.vue";
import { useAudioLevel } from "../../composables/useAudioLevel";
import { useFrame } from "../../composables/useFrame";
import { useTelemetry } from "../../composables/useTelemetry";
import { SLEEP_MS, WAKE_MS, useAssistantState } from "../../stores/assistant";
import HudBeam from "./HudBeam.vue";
import HudChrome from "./HudChrome.vue";
import HudGrid from "./HudGrid.vue";
import VoiceOrb from "./VoiceOrb.vue";

const ev = useAssistantState();

// Wired here rather than in the chrome: the chrome takes what it draws as
// props, so it can be mounted on its own with numbers made up on the spot.
const { data: telemetry, pending: telemetryPending, error: telemetryError } =
  useTelemetry();

// Measured once, here, and put in the store: the orb reads it as a prop, and
// anything else that wants it later reads the same number rather than opening
// a second AnalyserNode. Nothing is attached yet, so this is the stub that
// keeps the orb alive in development.
const audio = useAudioLevel();
watch(audio.level, (loud) => {
  // Quantised on the way into the store. The level changes every frame and
  // the store is reactive, so writing all of it would re-run the render of
  // everything reading it sixty times a second to say something the orb's own
  // smoothing cannot show.
  if (Math.abs(loud - ev.audioLevel) > 0.02) ev.audioLevel = loud;
});

/// Where each panel goes. The grid names are short because they have to line
/// up in a template-areas block and `conversation` is nine characters wider
/// than the column it sits in.
const SLOTS: { name: string; area: string }[] = [
  { name: "ticker", area: "ticker" },
  { name: "camera", area: "camera" },
  { name: "conversation", area: "conv" },
  { name: "media", area: "media" },
  { name: "web", area: "web" },
  { name: "headlines", area: "heads" },
  { name: "chart", area: "chart" },
];

// --- the one number ------------------------------------------------------

const still = window.matchMedia("(prefers-reduced-motion: reduce)");

/// 0 is the clock, 1 is the instrument, and everything between is the
/// transition, in whichever direction it is currently going.
const progress = ref(0);
const target = ref(0);

/// What is left of the transition when the machine has asked for less of it:
/// a plain cross-fade, no beam and no journey.
const CALM_MS = 300;

watch(
  () => ev.awake,
  (awake) => (target.value = awake ? 1 : 0),
);

useFrame((_, delta) => {
  if (progress.value === target.value) return;
  // Undoing is faster than doing. Leaving a screen should not feel like a
  // ceremony.
  const span = still.matches ? CALM_MS : target.value === 1 ? WAKE_MS : SLEEP_MS;
  const step = delta / span;
  progress.value =
    target.value === 1
      ? Math.min(1, progress.value + step)
      : Math.max(0, progress.value - step);
});

function clamp(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/// A slice of the whole, as its own 0..1.
function phase(from: number, to: number): number {
  return clamp((progress.value - from) / (to - from));
}

const easeOut = (t: number) => 1 - (1 - t) ** 3;
const easeInOut = (t: number) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2);

/// The orb's one outward push, over the first hundred milliseconds. The
/// scatter that goes with it is the WAKING look, inside the orb itself.
const pulse = computed(() => (still.matches ? 0 : Math.sin(phase(0, 0.11) * Math.PI)));

/// The beam, and therefore the reveal: 600 of the 900ms, eased out, so it
/// arrives at the bottom edge slowing rather than hitting it.
const sweep = computed(() =>
  // Nothing to uncover when there is no beam: the masks are told they are
  // already done, and the two screens simply swap underneath.
  still.matches ? target.value : easeOut(phase(0.11, 0.78)),
);

/// The journey to the corner, overlapping the end of the sweep.
const travel = computed(() =>
  still.matches ? target.value : easeInOut(phase(0.42, 1)),
);

/// The clock and its field, gone well before the beam reaches the bottom --
/// or, with no beam, over the whole of the cross-fade.
const resting = computed(() =>
  still.matches ? 1 - progress.value : 1 - clamp(progress.value / 0.34),
);

/// The instrument arriving. It leads the clock's departure, so there is never
/// a frame of bare background between the two.
const arrived = computed(() =>
  still.matches ? progress.value : Math.min(1, progress.value * 4),
);

/// Whether the beam is on screen at all.
const sweeping = computed(
  () => !still.matches && progress.value > 0 && progress.value < 1,
);

/// Each panel's own arrival, 60ms after the one before -- which, out of 900,
/// is this much of the whole. Eight of them need 480ms, so they begin while
/// the beam is still travelling rather than after it lands: waiting would
/// leave the last four still arriving when the transition is already over,
/// which is to say never arriving at all.
const STAGGER = 60 / WAKE_MS;
const FIRST_PANEL = 0.42;
const PANEL_FADE = 0.11;

function arriving(index: number): Record<string, string> {
  const at = clamp((progress.value - (FIRST_PANEL + index * STAGGER)) / PANEL_FADE);
  return {
    opacity: String(at),
    // From 0.98, so it settles into place rather than growing into it.
    transform: `scale(${0.98 + at * 0.02})`,
  };
}

// --- keys ----------------------------------------------------------------

function onKey(event: KeyboardEvent) {
  const pressed = event.target as HTMLElement | null;
  // A spacebar inside something being typed into is a space.
  const typing =
    pressed instanceof HTMLInputElement ||
    pressed instanceof HTMLTextAreaElement ||
    pressed?.isContentEditable === true;
  if (typing) return;

  if (event.code === "Space") {
    event.preventDefault();
    // Standing in for the wake word until the core's own wake loop reaches
    // this store. One key, one direction each way.
    if (ev.state === "IDLE") ev.triggerWake();
    else ev.sleep();
    return;
  }

  if (event.key === "Escape" && ev.state !== "IDLE") ev.sleep();
  else ev.touch();
}

onMounted(() => {
  // The stylesheet still carries the old view's flat grid; this says which
  // display is on screen so the two backgrounds never stack.
  document.documentElement.classList.add("hud-on");
  window.addEventListener("keydown", onKey);
  window.addEventListener("pointerdown", ev.touch);
});

onBeforeUnmount(() => {
  document.documentElement.classList.remove("hud-on");
  window.removeEventListener("keydown", onKey);
  window.removeEventListener("pointerdown", ev.touch);
});
</script>

<template>
  <main class="surface" :class="ev.state.toLowerCase()">
    <!-- The instrument, underneath. The beam uncovers it; it does not fly in
         from anywhere. -->
    <section
      v-if="progress > 0"
      class="hud"
      :style="{ opacity: arrived }"
    >
      <HudGrid :reveal="sweep" :sweeping="sweeping" />
      <HudChrome
        :telemetry="telemetry"
        :pending="telemetryPending"
        :error="telemetryError"
        :reveal="sweep"
      />

      <div class="stage">
        <div
          v-for="(slot, index) in SLOTS"
          :key="slot.name"
          class="slot"
          :style="{ gridArea: slot.area, ...arriving(index) }"
        >
          <span class="slot-name">{{ slot.name }}</span>
        </div>
        <div class="slot dock" :style="{ gridArea: 'dock', ...arriving(SLOTS.length) }">
          <span class="slot-name">dock</span>
        </div>
      </div>
    </section>

    <!-- The clock, over it, going as the beam comes down. -->
    <section v-if="resting > 0" class="idle" :style="{ opacity: resting }">
      <TheClock />
    </section>

    <!-- One orb, which travels. Two orbs -- one fading out at the centre and
         one fading in at the corner -- is a cut, not a journey. -->
    <div class="orb-layer" :style="{ '--travel': travel, '--pulse': pulse }">
      <VoiceOrb
        :level="ev.audioLevel"
        :state="ev.state"
        :size="180"
        :docked="travel > 0.9"
      />
    </div>

    <HudBeam v-if="sweeping" :at="sweep" />
  </main>
</template>

<style scoped>
.surface {
  position: fixed;
  inset: 0;
  height: 100dvh;
  overflow: hidden;
  user-select: none;
}

/* --- idle ------------------------------------------------------------- */

.idle {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* The orb is not in here -- it has to outlive this element -- so the clock
     is pushed down past the room the orb occupies above it. */
  padding-top: 250px;
  box-sizing: border-box;
  /* Void at the middle, a little more navy at the edges, and a vignette over
     the lot. The opposite of the HUD, which is brightest where the panels
     are. */
  background:
    radial-gradient(120% 120% at 50% 50%, transparent 55%, rgba(0, 0, 0, 0.5) 100%),
    radial-gradient(90% 90% at 50% 48%, var(--bg-void) 30%, #070d1a 100%);
}

/* --- the orb's journey ------------------------------------------------ */

/* From the centre of the screen -- lifted, so the clock has the room
   underneath -- to the bottom-right corner at 110px. All of it transform and
   none of it layout: this runs every frame for the length of the transition.

   The two distances are the difference between where the orb's centre starts
   and where the badge's centre belongs. The corner it belongs in is kept
   clear of the grid -- the last two rows stop at column eleven -- because a
   badge sitting on top of the chart is not docked, it is in the way. */
.orb-layer {
  --dx: calc(50dvw - 63px);
  --dy: calc(50dvh + 29px);
  position: absolute;
  top: 50%;
  left: 50%;
  width: 180px;
  height: 180px;
  margin: -90px 0 0 -90px;
  z-index: 3;
  transform: translateY(-110px)
    translate(calc(var(--travel) * var(--dx)), calc(var(--travel) * var(--dy)))
    scale(calc((1 - var(--travel) * 0.389) * (1 + var(--pulse) * 0.1)));
  will-change: transform;
}

/* --- active ----------------------------------------------------------- */

.hud {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: var(--bg-hud);
}

/* Twelve columns, twelve rows, and the panels placed by name. The
   conversation gets the middle and most of the height because it is the only
   panel anybody actually reads. */
.stage {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: grid;
  padding: 34px 30px 26px;
  box-sizing: border-box;
  gap: var(--gap);
  grid-template-columns: repeat(12, 1fr);
  grid-template-rows: repeat(12, 1fr);
  grid-template-areas:
    "ticker ticker ticker ticker ticker ticker .      .      .      web    web    web"
    "camera camera camera conv   conv   conv   conv   conv   conv   web    web    web"
    "camera camera camera conv   conv   conv   conv   conv   conv   web    web    web"
    "camera camera camera conv   conv   conv   conv   conv   conv   web    web    web"
    "camera camera camera conv   conv   conv   conv   conv   conv   web    web    web"
    "media  media  media  conv   conv   conv   conv   conv   conv   heads  heads  heads"
    "media  media  media  conv   conv   conv   conv   conv   conv   heads  heads  heads"
    "media  media  media  conv   conv   conv   conv   conv   conv   heads  heads  heads"
    "media  media  media  conv   conv   conv   conv   conv   conv   heads  heads  heads"
    ".      .      .      conv   conv   conv   conv   conv   conv   heads  heads  heads"
    ".      .      .      dock   dock   dock   dock   dock   dock   chart  chart  ."
    ".      .      .      dock   dock   dock   dock   dock   dock   chart  chart  .";
}

/* Empty, for now: a dashed outline with the name of what belongs in it, so
   the geometry can be judged before anything has been built into it. */
.slot {
  display: grid;
  place-items: center;
  border: 1px dashed rgba(120, 180, 255, 0.16);
  min-height: 0;
  min-width: 0;
}

.slot-name {
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: var(--label-track);
  text-transform: uppercase;
  color: var(--text-dim);
}

.dock {
  border-style: none;
  align-self: end;
}

/* Asked not to animate: the beam never renders, the journey is not run, and
   the two screens cross-fade instead. */
@media (prefers-reduced-motion: reduce) {
  .idle,
  .hud {
    transition: opacity 0.3s ease;
  }
}
</style>
