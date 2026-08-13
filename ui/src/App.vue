<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { canBindKeys, dismiss, inApp } from "./api";
import HudPanel from "./components/HudPanel.vue";
import StateDot from "./components/StateDot.vue";
import TheAnswer from "./components/TheAnswer.vue";
import TheAppearance from "./components/TheAppearance.vue";
import TheComposer from "./components/TheComposer.vue";
import TheHints from "./components/TheHints.vue";
import TheHistory from "./components/TheHistory.vue";
import TheQuestion from "./components/TheQuestion.vue";
import TheSettings from "./components/TheSettings.vue";
import { useAppearance } from "./stores/appearance";
import { useSession } from "./stores/session";

const session = useSession();
const appearance = useAppearance();
const composer = ref<InstanceType<typeof TheComposer> | null>(null);

const quiet = computed(
  () =>
    !session.question &&
    !session.camera &&
    !session.heard &&
    !session.said.length &&
    !session.trouble,
);

/// The key as it is printed on it, not as the plugin spells it.
const shortcut = computed(() =>
  session.shortcut
    .split("+")
    .map(
      (part) =>
        ({ CmdOrCtrl: "⌘", Cmd: "⌘", Ctrl: "⌃", Alt: "⌥", Shift: "⇧" })[part] ??
        part,
    )
    .join(""),
);

onMounted(() => {
  session.load();
  session.refresh();

  // Escape puts the window away. It does not answer anything: a turn waiting
  // on a confirmation is still waiting when it comes back.
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !session.question) void dismiss();
  });

  window.addEventListener("focus", () => composer.value?.take());
});
</script>

<template>
  <main :class="{ app: inApp }">
    <!-- The chrome is the handle: there is no title bar to drag. -->
    <header class="chrome" data-drag>
      <span class="mark">E.V.</span>
      <StateDot :state="session.state" />
      <span class="state">{{ session.state }}</span>
      <span class="grow" />
      <span v-if="canBindKeys && session.shortcut" class="key">{{ shortcut }}</span>
      <span class="mode">{{ appearance.resolved }}</span>
    </header>

    <div class="grid">
      <div class="column">
        <HudPanel label="Ask" :live="session.state !== 'idle'">
          <template #aside>
            <span class="locale">{{ session.locale }}</span>
          </template>
          <TheComposer ref="composer" />
        </HudPanel>

        <HudPanel
          label="Answer"
          :live="Boolean(session.question) || session.camera"
          class="grows"
        >
          <TheQuestion />
          <TheAnswer />
          <TheHints v-if="quiet" @pick="composer?.suggest($event)" />
        </HudPanel>
      </div>

      <div class="column side">
        <HudPanel label="Trail" class="grows">
          <TheHistory />
        </HudPanel>

        <HudPanel label="Settings">
          <TheSettings />
        </HudPanel>

        <HudPanel label="Appearance">
          <TheAppearance />
        </HudPanel>
      </div>
    </div>
  </main>
</template>

<style scoped>
main {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  padding: 14px 16px 16px;
  min-height: 100vh;
  box-sizing: border-box;
}

/* In the app the window is the display: it fills it. In a browser it is a
   page, so it stops growing and stays legible. */
main.app {
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

main:not(.app) {
  max-width: 1080px;
  margin: 0 auto;
}

.chrome {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--faint);
  user-select: none;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.mark {
  color: var(--ink);
  letter-spacing: 0.3em;
  text-shadow: 0 0 12px rgba(var(--accent), 0.45);
}

.grow {
  flex: 1;
}

.key,
.mode {
  border: 1px solid var(--line);
  border-radius: 2px;
  padding: 2px 6px;
}

.grid {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: var(--gap);
  flex: 1;
  min-height: 0;
}

.column {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  min-height: 0;
}

.grows {
  flex: 1;
  min-height: 0;
}

.locale {
  font-family: var(--mono);
  color: var(--faint);
}

/* One column when there is not room for two: the browser page on a laptop
   half-screen, and the panel if it is ever made narrow. */
@media (max-width: 760px) {
  .grid {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
}
</style>
