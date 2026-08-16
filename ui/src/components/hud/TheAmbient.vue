<script setup lang="ts">
// The resting stage: a sphere, a clock, and nothing else at all.
//
// Not an instrument. This is the display left alone in a dark room, so the
// room light comes up, the grid goes, the dock goes, the cursor goes, and
// what is left is something to glance at from across the room -- which is
// what makes the clock the largest type anywhere in this interface and the
// date the smallest.

import { onBeforeUnmount, onMounted, ref } from "vue";
import PlasmaOrb from "./PlasmaOrb.vue";

const props = withDefaults(
  defineProps<{
    level?: number;
    /// The language the date is written in. E.V. answers in the language it
    /// was asked in, and the date it leaves on the wall should match.
    locale?: string;
  }>(),
  { level: 0, locale: "pt-PT" },
);

const time = ref("");
const date = ref("");
let timer = 0;

function tick() {
  const now = new Date();
  time.value = now.toLocaleTimeString(props.locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  date.value = now.toLocaleDateString(props.locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

onMounted(() => {
  tick();
  // A quarter-minute poll: right for a display that shows minutes, and
  // nothing here is worth a per-second wake-up on a screen nobody is at.
  timer = window.setInterval(tick, 15_000);
});

onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <section class="ambient">
    <div class="orb">
      <PlasmaOrb :level="level" />
    </div>
    <p class="time">{{ time }}</p>
    <p class="date">{{ date }}</p>
  </section>
</template>

<style scoped>
.ambient {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, 2vh, 26px);
  user-select: none;
}

.orb {
  width: min(58vh, 58vw);
  height: min(58vh, 58vw);
  /* Centre-top: the clock wants the room underneath it, and a sphere sitting
     dead centre with type below reads as bottom-heavy. */
  margin-top: -4vh;
}

/* The largest type in the interface, and the only place Exo 2 is used. */
.time {
  margin: 0;
  font-family: var(--clock-font);
  font-size: clamp(56px, 9vmin, 96px);
  font-weight: 600;
  letter-spacing: 0.15em;
  /* The tracking is added after the last digit too. */
  text-indent: 0.15em;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  color: #fff;
  text-shadow: 0 0 32px rgba(120, 170, 230, 0.35);
}

.date {
  margin: 0;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.32em;
  text-indent: 0.32em;
  text-transform: uppercase;
  color: rgba(232, 240, 250, 0.55);
}
</style>
