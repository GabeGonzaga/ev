<script setup lang="ts">
// The furniture: an edge scale, a notch, corner brackets, and two short
// readings tucked into the bottom corners.
//
// None of it does anything, and that is the point. An instrument is legible
// partly because of the marks around what it is measuring -- the scale on a
// rangefinder, the frame on a viewfinder -- and a screen with only content on
// it reads as a web page. This is the frame, and on the blank stage it is the
// only thing there, so it has to look intentional on its own.
//
// Nothing here is interactive and nothing here should ever be: it sits over
// the whole display, so it declines the pointer entirely.

import { computed } from "vue";
import { asUptime, type Telemetry } from "../../composables/useTelemetry";

const props = withDefaults(
  defineProps<{
    telemetry: Telemetry | null;
    pending?: boolean;
    error?: string | null;
  }>(),
  { pending: false, error: null },
);

/// Bottom left: what E.V. is running on. Bottom right: how it is doing.
/// Short, because nobody reads these -- they glance to see that they are
/// still moving, and read them only on the day something is wrong.
const left = computed(() => {
  if (props.error) return "CORE UNREACHABLE";
  if (!props.telemetry) return "";
  return `EV · ${props.telemetry.model}`.toUpperCase();
});

const right = computed(() => {
  if (props.error) return props.error.toUpperCase();
  if (!props.telemetry) return "";
  return `${asUptime(props.telemetry.uptime)} · ${props.telemetry.latency}MS`;
});
</script>

<template>
  <div class="chrome" aria-hidden="true">
    <!-- A rangefinder scale down the left edge. Gradients rather than several
         hundred elements: the browser draws these as one paint, and nothing
         here ever changes. -->
    <div class="ruler" />

    <!-- The notch: steps down, across and back up. It marks the middle of the
         top edge, and that is its whole job. -->
    <svg class="notch" viewBox="0 0 240 22" fill="none">
      <polyline
        points="0,1 86,1 96,17 144,17 154,1 240,1"
        stroke="var(--neon-dim)"
        stroke-width="1"
      />
      <polyline points="96,17 144,17" stroke="var(--neon)" stroke-width="1" />
    </svg>

    <span class="corner tl" />
    <span class="corner tr" />
    <span class="corner bl" />
    <span class="corner br" />

    <p class="reading at-left" :class="{ failed: error }">{{ left }}</p>
    <p class="reading at-right" :class="{ failed: error }">{{ right }}</p>
  </div>
</template>

<style scoped>
.chrome {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
  font-family: var(--mono);
}

/* Every tick 12px, every fifth longer and brighter -- two gradients stacked,
   the long one drawn over the short one. */
.ruler {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 14px;
  background-image:
    repeating-linear-gradient(to bottom, var(--neon-dim) 0 1px, transparent 1px 60px),
    repeating-linear-gradient(
      to bottom,
      rgba(200, 224, 245, 0.22) 0 1px,
      transparent 1px 12px
    );
  background-size: 13px 100%, 6px 100%;
  background-repeat: no-repeat, no-repeat;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent,
    #000 14%,
    #000 86%,
    transparent
  );
  mask-image: linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent);
}

.notch {
  position: absolute;
  top: 0;
  left: 50%;
  width: 240px;
  margin-left: -120px;
}

/* Four L-brackets, one per corner, drawn with two borders each. */
.corner {
  position: absolute;
  width: 18px;
  height: 18px;
  border: 0 solid var(--neon-dim);
}

.corner.tl {
  top: 10px;
  left: 10px;
  border-top-width: 1px;
  border-left-width: 1px;
}

.corner.tr {
  top: 10px;
  right: 10px;
  border-top-width: 1px;
  border-right-width: 1px;
}

.corner.bl {
  bottom: 10px;
  left: 10px;
  border-bottom-width: 1px;
  border-left-width: 1px;
}

.corner.br {
  bottom: 10px;
  right: 10px;
  border-bottom-width: 1px;
  border-right-width: 1px;
}

/* Tucked in, small and dim. Two short readings rather than one dense strip:
   a line of telemetry across the whole bottom edge is a status bar, and this
   display does not have one. */
.reading {
  position: absolute;
  bottom: 12px;
  margin: 0;
  font-size: var(--telemetry);
  letter-spacing: 0.16em;
  color: var(--text-dim);
  white-space: nowrap;
}

.at-left {
  left: 36px;
}

.at-right {
  right: 36px;
}

.reading.failed {
  color: var(--error);
}
</style>
