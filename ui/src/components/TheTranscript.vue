<script setup lang="ts">
import { useSession } from "../stores/session";

defineProps<{ suppressed?: boolean }>();

const session = useSession();
</script>

<template>
  <!-- Transient, positioned relative to the orb, never in a panel. Suppressed
       entirely while the chat widget is open: it is already showing this, and
       two copies of the same sentence looks like a bug. -->
  <div v-if="!suppressed" class="transcript">
    <p v-if="session.heard" class="heard">{{ session.heard }}</p>
    <p v-for="line in session.said" :key="line" class="said">{{ line }}</p>
    <p v-if="session.trouble" class="trouble">{{ session.trouble }}</p>
  </div>
</template>

<style scoped>
.transcript {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  max-width: 620px;
  text-align: center;
  font-family: var(--system);
}

.heard {
  margin: 0;
  font-size: 15px;
  color: rgba(242, 245, 248, 0.6);
}

.said {
  margin: 0;
  font-size: 17px;
  line-height: 1.5;
  color: rgba(242, 245, 248, 0.92);
}

.trouble {
  margin: 0;
  font-size: 14px;
  color: var(--error);
}
</style>
