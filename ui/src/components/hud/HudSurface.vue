<script setup lang="ts">
// The display: one screen, two faces.
//
// IDLE is a clock and an orb on a dark field. ACTIVE is the instrument. They
// are the same surface rather than two pages, because the transition between
// them is the thing worth building -- a router would make it a navigation,
// and a navigation cannot be reversed in 500ms with a beam.
//
// Fixed to the viewport and never scrolls. A HUD that scrolls is a document.

import { onBeforeUnmount, onMounted } from "vue";
import TheClock from "../TheClock.vue";
import { useTelemetry } from "../../composables/useTelemetry";
import { useAssistantState } from "../../stores/assistant";
import HudChrome from "./HudChrome.vue";
import HudGrid from "./HudGrid.vue";

const ev = useAssistantState();

// Wired here rather than in the chrome: the chrome takes what it draws as
// props, so it can be mounted on its own with numbers made up on the spot.
const { data: telemetry, pending: telemetryPending, error: telemetryError } =
  useTelemetry();

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

function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null;
  // A spacebar inside something being typed into is a space.
  const typing =
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target?.isContentEditable === true;
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
    <!-- IDLE: the clock, the orb, and nothing else at all. -->
    <section v-if="!ev.awake" class="idle">
      <!-- The orb lands here in step 2; until then this is the room it will
           need, at the size it will be. -->
      <div class="orb-slot">
        <p class="wordmark">EV</p>
      </div>
      <TheClock />
    </section>

    <!-- ACTIVE: the instrument. -->
    <section v-else class="hud">
      <HudGrid />
      <HudChrome
        :telemetry="telemetry"
        :pending="telemetryPending"
        :error="telemetryError"
      />

      <div class="stage">
        <div
          v-for="slot in SLOTS"
          :key="slot.name"
          class="slot"
          :style="{ gridArea: slot.area }"
        >
          <span class="slot-name">{{ slot.name }}</span>
        </div>
        <div class="slot dock" style="grid-area: dock">
          <span class="slot-name">dock</span>
        </div>
      </div>
    </section>
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
  gap: clamp(18px, 5vh, 46px);
  /* Void at the middle, a little more navy at the edges, and a vignette over
     the lot. The opposite of the HUD, which is brightest where the panels
     are. */
  background:
    radial-gradient(120% 120% at 50% 50%, transparent 55%, rgba(0, 0, 0, 0.5) 100%),
    radial-gradient(90% 90% at 50% 48%, var(--bg-void) 30%, #070d1a 100%);
}

.orb-slot {
  display: grid;
  place-items: center;
  width: 180px;
  height: 180px;
}

/* One of the two things on this display allowed to be pure white. */
.wordmark {
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.42em;
  text-indent: 0.42em;
  color: #fff;
  text-shadow: var(--neon-glow-text);
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
    ".      .      .      dock   dock   dock   dock   dock   dock   chart  chart  chart"
    ".      .      .      dock   dock   dock   dock   dock   dock   chart  chart  chart";
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
</style>
