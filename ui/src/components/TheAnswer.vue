<script setup lang="ts">
import { computed } from "vue";
import { useSession } from "../stores/session";

const session = useSession();

// Nothing to say yet is nothing on screen: an empty box under the input is a
// promise the panel has not kept.
const shown = computed(
  () =>
    session.camera ||
    Boolean(session.heard) ||
    session.said.length > 0 ||
    Boolean(session.trouble),
);
</script>

<template>
  <div v-if="shown" class="answer">
    <!-- Invariant 8, the visible half. macOS lights its own indicator; this
         one says which application did it, and goes out with the camera. -->
    <p v-if="session.camera" class="camera">
      <span class="live" /> the camera is on
    </p>

    <!-- What E.V. heard, shown even when it is right: being misheard should
         be visible in the words rather than inferred from the wrong action. -->
    <p v-if="session.heard" class="heard">{{ session.heard }}</p>

    <p v-for="line in session.said" :key="line" class="said">{{ line }}</p>

    <p v-if="session.trouble" class="trouble">{{ session.trouble }}</p>
  </div>
</template>

<style scoped>
.answer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.heard {
  margin: 0;
  font-family: var(--mono);
  font-size: 10.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--faint);
}

.said {
  margin: 0;
  font-size: 17px;
  font-weight: var(--display);
  letter-spacing: 0.03em;
  line-height: 1.45;
}

.trouble {
  margin: 0;
  font-size: 13px;
  color: var(--bad);
  font-family: var(--mono);
  word-break: break-word;
}

.camera {
  margin: 0 0 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--live);
  display: flex;
  align-items: center;
  gap: 6px;
}

.live {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--live);
  animation: blink 1.2s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
