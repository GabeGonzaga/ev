<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { canBindKeys, dismiss, hasWindowControls, inApp, windowControl } from "./api";
import HudPanel from "./components/HudPanel.vue";
import HudWindow from "./components/HudWindow.vue";
import StateDot from "./components/StateDot.vue";
import TheActions from "./components/TheActions.vue";
import TheAnswer from "./components/TheAnswer.vue";
import TheAppearance from "./components/TheAppearance.vue";
import TheBeam from "./components/TheBeam.vue";
import TheClock from "./components/TheClock.vue";
import TheComposer from "./components/TheComposer.vue";
import TheConsole from "./components/TheConsole.vue";
import TheCore from "./components/TheCore.vue";
import TheDock from "./components/TheDock.vue";
import TheHints from "./components/TheHints.vue";
import TheHistory from "./components/TheHistory.vue";
import TheMusic from "./components/TheMusic.vue";
import TheQuestion from "./components/TheQuestion.vue";
import TheSettings from "./components/TheSettings.vue";
import { useAppearance } from "./stores/appearance";
import { useLayout } from "./stores/layout";
import { useSession } from "./stores/session";
import { useWindows } from "./stores/windows";

const session = useSession();
const appearance = useAppearance();
const layout = useLayout();
const windows = useWindows();

/// Where each floating window opens the first time, and how big. Kept here
/// with the windows themselves so the store stays about geometry, not about
/// which widgets exist. Off by default: the display starts as the orb, and a
/// window is there because the dock was asked for it.
const SPAWN = {
  console: { x: 40, y: 96, w: 340, h: 300 },
  music: { x: 300, y: 380, w: 384, h: 224 },
  settings: { x: 80, y: 150, w: 340, h: 260 },
} as const;
const FLOATING = Object.keys(SPAWN);
const composer = ref<InstanceType<typeof TheComposer> | null>(null);

/// Nothing on screen but the ring: no bars, no widgets, no chrome.
///
/// A state rather than a different application. E.V. spends most of its life
/// waiting, and what it should look like while waiting is not what it should
/// look like while being read from.
const ambient = ref(false);

async function rest(on: boolean) {
  ambient.value = on;
  // The window goes with it: a display with nothing on it should not be
  // sharing the screen with the thing it was covering.
  await windowControl("fullscreen");
}

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

/// Every widget this layout has. The store checks what it remembered against
/// this, so a name from an older arrangement cannot leave the display empty.
const WIDGETS = ["Ask", "Trail", "Console", "Settings", "Appearance"];

onMounted(() => {
  layout.reconcile(WIDGETS);
  windows.reconcile(FLOATING);
  session.load();
  session.refresh();

  // Escape puts the window away. It does not answer anything: a turn waiting
  // on a confirmation is still waiting when it comes back.
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    // One key, the nearest thing first: leave the resting screen, then give
    // the display back, then put the window away.
    if (ambient.value) return void rest(false);
    if (layout.focused !== null) return layout.release();
    if (!session.question) void dismiss();
  });

  window.addEventListener("focus", () => composer.value?.take());
});
</script>

<template>
  <!-- The sweep that answers the name, over everything. It renders only while
       it falls, so at rest it is not there at all. -->
  <TheBeam />

  <!-- The floating widgets, over the grid and the orb. The layer itself lets
       clicks through; only the windows on it catch them, so the app beneath
       stays reachable where no window covers it. Each renders only while open;
       the dock opens them. -->
  <div class="floating">
    <HudWindow id="console" label="console" :spawn="SPAWN.console" :live="session.state !== 'idle'">
      <TheConsole />
    </HudWindow>

    <HudWindow id="music" label="apple_music" :spawn="SPAWN.music">
      <TheMusic />
    </HudWindow>

    <HudWindow id="settings" label="settings" :spawn="SPAWN.settings">
      <TheSettings />
    </HudWindow>
  </div>

  <TheDock />

  <!-- Resting: the orb and the clock beneath it, and nothing else at all. -->
  <main v-if="ambient" class="resting" @click="rest(false)">
    <TheCore :state="session.state" ambient>
      <TheAnswer />
    </TheCore>
    <TheClock />
  </main>

  <main v-else :class="{ app: inApp }">
    <!-- The chrome is the handle: there is no title bar to drag. -->
    <header class="chrome" data-drag>
      <div v-if="hasWindowControls" class="lights">
        <button class="close" type="button" title="close" @click="windowControl('close')" />
        <button
          class="minimise"
          type="button"
          title="minimise"
          @click="windowControl('minimise')"
        />
        <button
          class="full"
          type="button"
          title="full screen"
          @click="windowControl('fullscreen')"
        />
      </div>

      <span class="mark">E.V.</span>
      <StateDot :state="session.state" />
      <span class="state">{{ session.state }}</span>
      <span class="grow" />
      <!-- Said where it can be seen, for as long as it is true. -->
      <span v-if="session.listening" class="ear" title="listening for the name">
        ◉ listening
      </span>
      <span v-if="canBindKeys && session.shortcut" class="key">{{ shortcut }}</span>
      <button class="mode rest" type="button" title="rest" @click="rest(true)">
        rest
      </button>
      <span class="mode">{{ appearance.resolved }}</span>
    </header>

    <div class="grid">
      <!-- The stage stays when the widget with the floor is the one that
           lives in it. Hiding the column that holds the button to come back
           is how it got stuck the first time. -->
      <div v-if="layout.shown('Ask')" class="column stage">
        <!-- The middle of the display: a ring that turns while E.V. is doing
             something, with whatever it has to say inside it. -->
        <TheCore v-if="layout.focused === null" :state="session.state">
          <!-- Inside the ring: the wordmark, and whatever E.V. has to say.
               Not what it is doing -- the chrome says that, and two labels in
               one circle is one label too many. -->
          <TheQuestion />
          <TheAnswer />
        </TheCore>

        <TheHints
          v-if="quiet && layout.focused === null"
          @pick="composer?.suggest($event)"
        />

        <!-- The quick row: music, camera, and a site to open. Under the orb,
             above the line you type into -- the reach-for-it things first. -->
        <TheActions v-if="layout.focused === null" />

        <HudPanel label="Ask" :live="session.state !== 'idle'" class="asking">
          <template #aside>
            <span class="locale">{{ session.locale }}</span>
          </template>
          <TheComposer ref="composer" />
        </HudPanel>
      </div>

      <div class="column side">
        <HudPanel v-if="layout.shown('Trail')" label="Trail" class="grows">
          <TheHistory />
        </HudPanel>

        <HudPanel v-if="layout.shown('Console')" label="Console" class="grows">
          <TheConsole />
        </HudPanel>

        <HudPanel v-if="layout.shown('Settings')" label="Settings">
          <TheSettings />
        </HudPanel>

        <HudPanel v-if="layout.shown('Appearance')" label="Appearance">
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

/* The canvas the floating windows live on: the whole viewport, transparent
   to clicks so the app underneath keeps working, with each window turning
   pointer events back on for itself. */
.floating {
  position: fixed;
  inset: 0;
  z-index: 40;
  pointer-events: none;
}

.floating > * {
  pointer-events: auto;
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

/* Squared, because everything here is. In the same order macOS uses them,
   so the muscle memory works. */
.lights {
  display: flex;
  gap: 6px;
  margin-right: 4px;
}

.lights button {
  width: 10px;
  height: 10px;
  border: 1px solid var(--line);
  opacity: 0.75;
  transition: opacity 0.15s, box-shadow 0.15s;
}

.lights button:hover {
  opacity: 1;
}

.lights .close {
  background: rgba(255, 95, 87, 0.85);
}

.lights .minimise {
  background: rgba(255, 189, 46, 0.85);
}

.lights .full {
  background: rgba(39, 201, 63, 0.85);
}

.mark {
  color: var(--ink);
  font-weight: var(--display);
  letter-spacing: 0.42em;
  text-shadow: 0 0 12px rgba(var(--accent), 0.45);
}

.grow {
  flex: 1;
}

.ear {
  color: var(--live);
  border: 1px solid var(--live);
  border-radius: 2px;
  padding: 2px 6px;
  animation: breathe 2s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

.key,
.mode {
  border: 1px solid var(--line);
  border-radius: 2px;
  padding: 2px 6px;
}

.rest {
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  color: var(--faint);
}

.rest:hover {
  color: var(--ink);
  border-color: var(--panel-lit);
}

/* Nothing else is on screen: the orb, and the clock under it, as one centred
   group. */
.resting {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(16px, 4vh, 40px);
  height: 100vh;
  padding: 0;
  cursor: none;
}

/* The orb sizes to itself here rather than filling the column, so the clock
   sits with it instead of being pushed to the floor. */
.resting :deep(.core) {
  flex: 0 0 auto;
}

.grid {
  display: grid;
  grid-template-columns: 1.45fr 1fr;
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

/* A widget given the floor takes the display, and the grid stops being a
   grid until it gives it back. */
.grid:has(.focused) {
  grid-template-columns: 1fr;
}

.grows:not(.folded) {
  flex: 1;
  min-height: 0;
}

.locale {
  font-family: var(--mono);
  color: var(--faint);
}

/* The ring, and under it the line you type into: a console sits below the
   display it belongs to. */
.stage {
  justify-content: space-between;
}

/* With the floor, the composer takes the room the ring was using. */
.grid:has(.focused) .asking {
  flex: 1;
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
