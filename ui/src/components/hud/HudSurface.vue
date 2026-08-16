<script setup lang="ts">
// The display: one surface, five stages.
//
// Not five screens. The contents change with the stage -- blank, idle,
// waking, awake, ambient -- on one full-screen surface, because the
// transitions between them are the thing worth building and a router would
// make each one a navigation.
//
// The default is empty. Nothing below the grid appears until it is summoned,
// and everything summoned can be put away again: the resting look of every
// stage is the stage with nothing on it.
//
// Fixed to the viewport and never scrolls. A HUD that scrolls is a document.

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useAudioLevel } from "../../composables/useAudioLevel";
import { useFrame } from "../../composables/useFrame";
import { useTelemetry } from "../../composables/useTelemetry";
import { SLEEP_MS, WAKE_MS, useAssistantState } from "../../stores/assistant";
import { useWorkspace } from "../../stores/workspace";
import CoreRing from "./CoreRing.vue";
import HudBeam from "./HudBeam.vue";
import HudChrome from "./HudChrome.vue";
import HudGrid from "./HudGrid.vue";
import WindowLights from "./WindowLights.vue";

const ev = useAssistantState();
const workspace = useWorkspace();

// Wired here rather than in the chrome: the chrome takes what it draws as
// props, so it can be mounted on its own with numbers made up on the spot.
const { data: telemetry, pending: telemetryPending, error: telemetryError } =
  useTelemetry();

// Measured once, here, and put in the store: the ring reads it as a prop, and
// anything else that wants it later reads the same number rather than opening
// a second AnalyserNode. Nothing is attached yet, so this is the stub that
// keeps the display alive in development.
const audio = useAudioLevel();
watch(audio.level, (loud) => {
  // Quantised on the way in. The level changes every frame and the store is
  // reactive, so writing all of it would re-render everything reading it
  // sixty times a second to say something no smoothing can show.
  if (Math.abs(loud - ev.audioLevel) > 0.02) ev.audioLevel = loud;
});

// --- the one number ------------------------------------------------------

const still = window.matchMedia("(prefers-reduced-motion: reduce)");

/// 0 is idle, 1 is awake, and everything between is the sweep in whichever
/// direction it is going. The band's height, the grid's brightness, the
/// chrome's arrival and the ring's glow are all functions of it -- five
/// clocks agreeing for 800ms is luck.
const swept = ref(0);
const target = ref(0);

/// What is left of the transition when the machine has asked for less of it:
/// a plain cross-fade, no band.
const CALM_MS = 260;

watch(
  () => ev.stage,
  (stage) => (target.value = stage === "waking" || stage === "awake" ? 1 : 0),
);

useFrame((_, delta) => {
  if (swept.value === target.value) return;
  const span = still.matches ? CALM_MS : target.value === 1 ? WAKE_MS : SLEEP_MS;
  const step = delta / span;
  swept.value =
    target.value === 1
      ? Math.min(1, swept.value + step)
      : Math.max(0, swept.value - step);
});

function clamp(value: number): number {
  return Math.min(1, Math.max(0, value));
}

// Quadratic, not cubic. A cubic ease-out puts the band 93% of the way down
// the screen in the first half of the window and leaves it crawling the last
// few pixels -- which reads as a flash followed by a wait rather than as one
// pass. Measured, not guessed: 380ms into an 820ms sweep had it at 0.974.
const easeOut = (t: number) => 1 - (1 - t) ** 2;

/// The band, and therefore the painting: it crosses in one pass, eased out,
/// so it arrives at the bottom edge slowing rather than hitting it.
const painted = computed(() =>
  // Calm still animates -- it just animates an opacity instead of a
  // boundary. Jumping to the target here would make "cross-fade instead" a
  // cut, which is the one thing it is not.
  still.matches ? swept.value : easeOut(clamp(swept.value / 0.88)),
);

/// How much neon is around the ring. The halo ramps in over the same window
/// the band is crossing, so the two land together rather than one waiting for
/// the other.
const lit = computed(() =>
  still.matches ? swept.value : clamp(swept.value * 1.15),
);

/// The band is on screen only while it is crossing -- one pass, then gone.
const sweeping = computed(
  () => !still.matches && swept.value > 0 && swept.value < 1,
);

/// The grid is on every stage except ambient, which lifts the room light and
/// has no business showing graph paper.
const gridded = computed(() => ev.stage !== "ambient");

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
    if (ev.stage === "awake") ev.rest();
    else ev.triggerWake();
    return;
  }

  // The specification gives the chat bar a keyboard shortcut as well as a
  // dock icon. The dock lands in step 5; this is the same store action.
  if (event.code === "KeyC" && !event.metaKey && !event.ctrlKey) {
    event.preventDefault();
    ev.toggle("console");
    return;
  }

  if (event.key === "Escape") {
    // Nearest thing first: the windows, then whatever is open, then the
    // display itself. An arrangement gone wrong has one key that undoes it.
    if (workspace.floating.length) workspace.dockAll();
    else if (ev.open.length) ev.open = [];
    else if (ev.stage !== "idle") ev.rest();
    return;
  }

  ev.touch();
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
  <main class="surface" :class="[ev.stage, { working: ev.working }]">
    <!-- Ambient lifts the room light and drops everything else; the other
         four stages share the near-black display and its grid. -->
    <div class="wash" :class="{ lifted: ev.stage === 'ambient' }" />

    <HudGrid v-if="gridded" :painted="painted" :calm="still.matches" />
    <HudChrome
      v-if="gridded"
      :telemetry="telemetry"
      :pending="telemetryPending"
      :error="telemetryError"
    />

    <!-- A frameless window with nothing to grab cannot be moved, and this
         display has no title bar. The top strip is the handle; the buttons on
         it opt out by the rule in the stylesheet. -->
    <div v-if="gridded" class="grab" data-drag>
      <WindowLights />
    </div>

    <!-- The core. Not on the blank stage, which is the grid on its own, and
         not in ambient, where the plasma orb takes its place. -->
    <CoreRing
      v-if="ev.ringed"
      :lit="lit"
      :voice="ev.voice"
      :level="ev.audioLevel"
      :working="ev.working"
    />

    <!-- The band. It is not laid over the transition, it *is* the
         transition: the same number that puts it at a height is the boundary
         the grid brightens across, so the light and what it lights cannot
         drift apart. -->
    <HudBeam v-if="sweeping" :at="painted" />

    <!-- The dock, the widgets and the ambient orb land here in the steps that
         follow. The stage is deliberately empty until they do. -->
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

/* Near-black, blue-leaning, darkest at the edges. Ambient lifts it to a
   softly lit blue-grey -- the one stage that is a presence in a room rather
   than an instrument on a desk. */
.wash {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 120% at 50% 48%, transparent 45%, rgba(0, 0, 0, 0.55) 100%),
    var(--page);
  transition: opacity 0.45s ease;
}

.wash.lifted {
  background: radial-gradient(
    75% 75% at 50% 42%,
    var(--ambient-core) 0%,
    var(--ambient-edge) 100%
  );
}

/* Tall enough to grab, short enough to stay above anything the stage puts
   near the top edge. */
.grab {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 30px;
  z-index: 4;
}

/* Nothing on screen, and the pointer out of the way with it. */
.surface.ambient {
  cursor: none;
}
</style>
