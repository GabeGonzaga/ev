<script setup lang="ts">
// The furniture: rulers, brackets, a notch, and a line of numbers.
//
// None of it does anything, and that is the point. An instrument is legible
// partly because of the marks around what it is measuring -- the scale on a
// rangefinder, the frame on a viewfinder -- and a screen with only content on
// it reads as a web page. This is the frame.
//
// Nothing in here is interactive and nothing in here should ever be: it sits
// over the whole display, so it declines the pointer entirely.

import { computed } from "vue";
import { asUptime, type Telemetry } from "../../composables/useTelemetry";

const props = defineProps<{
  telemetry: Telemetry | null;
  pending: boolean;
  error: string | null;
}>();

/// Dense, uppercase, and dull. Nobody reads this; they check that it is
/// moving, and they read it only on the day something is wrong.
const strip = computed(() => {
  const found = props.telemetry;
  if (!found) return "";
  return [
    `UP ${asUptime(found.uptime)}`,
    `MODEL ${found.model}`,
    `RTT ${found.latency}MS`,
    `MIC ${found.mic}`,
    `LINK ${found.connection}`,
  ]
    .join("  //  ")
    .toUpperCase();
});
</script>

<template>
  <div class="chrome" aria-hidden="true">
    <!-- Rangefinder scales down the left edge and across the top. Gradients
         rather than several hundred elements: the browser draws these as one
         paint each, and nothing here ever changes. -->
    <div class="ruler left" />
    <div class="ruler top" />

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

    <!-- The bottom edge. Loading and failure are printed here rather than
         hidden: an instrument that goes quiet when its telemetry breaks is
         worse than one that says so. -->
    <p class="telemetry" :class="{ failed: error }">
      <template v-if="error">TELEMETRY UNAVAILABLE // {{ error }}</template>
      <template v-else-if="pending">&gt; awaiting telemetry<span class="caret" /></template>
      <template v-else>{{ strip }}</template>
    </p>
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

/* Every tick 12px, every fifth one longer and brighter -- two gradients
   stacked, the long one drawn over the short one. */
.ruler {
  position: absolute;
  opacity: 0.9;
}

.ruler.left {
  top: 0;
  bottom: 0;
  left: 0;
  width: 14px;
  background-image:
    repeating-linear-gradient(
      to bottom,
      var(--neon-dim) 0 1px,
      transparent 1px 60px
    ),
    repeating-linear-gradient(to bottom, var(--hud-line) 0 1px, transparent 1px 12px);
  background-size: 13px 100%, 6px 100%;
  background-repeat: no-repeat, no-repeat;
  -webkit-mask-image: linear-gradient(to bottom, transparent, #000 12%, #000 88%, transparent);
  mask-image: linear-gradient(to bottom, transparent, #000 12%, #000 88%, transparent);
}

.ruler.top {
  left: 0;
  right: 0;
  top: 0;
  height: 14px;
  background-image:
    repeating-linear-gradient(to right, var(--neon-dim) 0 1px, transparent 1px 60px),
    repeating-linear-gradient(to right, var(--hud-line) 0 1px, transparent 1px 12px);
  background-size: 100% 13px, 100% 6px;
  background-repeat: no-repeat, no-repeat;
  /* Fades at both ends, and steps aside in the middle so the notch has the
     top edge to itself. */
  -webkit-mask-image: linear-gradient(
    to right,
    transparent,
    #000 12%,
    #000 calc(50% - 130px),
    transparent calc(50% - 118px),
    transparent calc(50% + 118px),
    #000 calc(50% + 130px),
    #000 88%,
    transparent
  );
  mask-image: linear-gradient(
    to right,
    transparent,
    #000 12%,
    #000 calc(50% - 130px),
    transparent calc(50% - 118px),
    transparent calc(50% + 118px),
    #000 calc(50% + 130px),
    #000 88%,
    transparent
  );
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

.telemetry {
  position: absolute;
  /* Clear of the corner brackets at both ends, which is why it starts at 36
     rather than at the padding. */
  left: 36px;
  right: 36px;
  bottom: 11px;
  margin: 0;
  font-size: var(--telemetry);
  letter-spacing: 0.14em;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.telemetry.failed {
  color: var(--error);
}

/* The block cursor every waiting thing in this UI uses. */
.caret {
  display: inline-block;
  width: 5px;
  height: 9px;
  margin-left: 4px;
  vertical-align: -1px;
  background: currentColor;
  animation: blink 1.1s steps(1) infinite;
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  50.01%,
  100% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .caret {
    animation: none;
  }
}
</style>
