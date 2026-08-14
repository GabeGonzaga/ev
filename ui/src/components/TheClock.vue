<script setup lang="ts">
// The clock beneath the orb on the resting screen. E.V. spends most of its
// life waiting; while it waits, the screen is a clock with a heartbeat.
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useSession } from "../stores/session";

const session = useSession();
const time = ref("");
const date = ref("");
let timer = 0;

function tick() {
  const now = new Date();
  // The session's locale, so the date reads in the same language E.V. answers
  // in -- pt-PT by default, not the browser's guess.
  time.value = now.toLocaleTimeString(session.locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  date.value = now.toLocaleDateString(session.locale, {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });
}

onMounted(() => {
  tick();
  // A quarter-minute poll: fine for a minute display, and nothing here is
  // worth a per-second wake-up.
  timer = window.setInterval(tick, 15000);
});

onBeforeUnmount(() => clearInterval(timer));
</script>

<template>
  <div class="clock">
    <p class="time">{{ time }}</p>
    <p class="date">{{ date }}</p>
  </div>
</template>

<style scoped>
.clock {
  text-align: center;
  user-select: none;
}

.time {
  margin: 0;
  font-family: var(--clock-font);
  font-weight: 200;
  font-size: clamp(40px, 8vmin, 66px);
  letter-spacing: 0.05em;
  font-variant-numeric: tabular-nums;
  color: var(--text);
  text-shadow: 0 0 24px rgba(var(--accent), 0.32);
}

.date {
  margin: 4px 0 0;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--muted);
}
</style>
