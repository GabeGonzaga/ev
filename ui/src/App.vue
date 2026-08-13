<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { dismiss, inApp } from "./api";
import StateDot from "./components/StateDot.vue";
import TheAnswer from "./components/TheAnswer.vue";
import TheComposer from "./components/TheComposer.vue";
import TheHints from "./components/TheHints.vue";
import TheHistory from "./components/TheHistory.vue";
import TheQuestion from "./components/TheQuestion.vue";
import TheSettings from "./components/TheSettings.vue";
import { useSession } from "./stores/session";

const session = useSession();
const composer = ref<InstanceType<typeof TheComposer> | null>(null);

const quiet = computed(
  () =>
    !session.question &&
    !session.camera &&
    !session.heard &&
    !session.said.length &&
    !session.trouble,
);

onMounted(() => {
  session.load();

  // Escape puts the panel away. It does not answer anything: a turn waiting on
  // a confirmation is still waiting when it comes back.
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !session.question) void dismiss();
  });

  // Summoned by a key, so it is ready for the next thing typed.
  window.addEventListener("focus", () => composer.value?.take());
});
</script>

<template>
  <main :class="{ app: inApp }">
    <!-- The header is the handle: there is no title bar to drag. -->
    <header data-drag>
      <StateDot :state="session.state" />
      <span class="state">{{ session.state }}</span>
      <span class="grow" />
      <span class="name">E.V.</span>
    </header>

    <TheComposer ref="composer" />
    <TheQuestion />
    <TheAnswer />

    <!-- Nothing has happened yet, so the space says what could. It goes the
         moment there is an answer to read. -->
    <TheHints v-if="quiet" @pick="composer?.suggest($event)" />

    <footer>
      <TheHistory />
      <TheSettings />
    </footer>
  </main>
</template>

<style scoped>
main {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  padding: 14px 16px 12px;
  min-height: 100vh;
  box-sizing: border-box;
}

/* In the app the window is the panel: it fills it, and macOS rounds it. */
main.app {
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

/* In a browser it is a page with a panel on it, not a panel stretched to the
   size of a tab. */
main:not(.app) {
  max-width: 640px;
  min-height: 0;
  margin: 40px auto;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--raised);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}

main:not(.app) footer {
  margin-top: 18px;
}

header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  user-select: none;
}

.state {
  text-transform: lowercase;
}

.grow {
  flex: 1;
}

.name {
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--faint);
}

footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--line);
  min-height: 0;
}
</style>
