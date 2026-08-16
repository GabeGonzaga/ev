<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import * as api from "./api";
import { canBindKeys, dismiss, hasWindowControls, inApp, windowControl } from "./api";
import HudPanel from "./components/HudPanel.vue";
import StateDot from "./components/StateDot.vue";
import TheAnswer from "./components/TheAnswer.vue";
import TheAppearance from "./components/TheAppearance.vue";
import TheClock from "./components/TheClock.vue";
import TheComposer from "./components/TheComposer.vue";
import TheConsole from "./components/TheConsole.vue";
import TheCore from "./components/TheCore.vue";
import TheHints from "./components/TheHints.vue";
import TheHistory from "./components/TheHistory.vue";
import TheOrb from "./components/TheOrb.vue";
import TheQuestion from "./components/TheQuestion.vue";
import TheSettings from "./components/TheSettings.vue";
import { useAppearance } from "./stores/appearance";
import { useLayout } from "./stores/layout";
import { useSession } from "./stores/session";

const session = useSession();
const appearance = useAppearance();
const layout = useLayout();
const composer = ref<InstanceType<typeof TheComposer> | null>(null);

/// Nothing on screen but the sphere: no bars, no widgets, no chrome.
///
/// A state rather than a different application. E.V. spends most of its life
/// waiting to be called, and what it should look like while waiting is not
/// what it should look like while being read from.
const ambient = ref(false);

// Called by name, so the waiting screen has stopped being the right one.
// What was asked for is about to arrive, and it arrives in the working view.
watch(
  () => session.woke,
  () => {
    if (ambient.value) void rest(false);
    composer.value?.take();
  },
);

/// Whether the waiting screen took the whole display when it was entered.
/// It does when it was asked for, and does not when E.V. started on it --
/// and leaving must give back only what was taken, or dismissing the sphere
/// puts the working view full screen instead.
const tookScreen = ref(false);

async function rest(on: boolean, whole = true) {
  ambient.value = on;
  const move = on ? whole : tookScreen.value;
  tookScreen.value = on && whole;
  // The window goes with it: a display with nothing on it should not be
  // sharing the screen with the thing it was covering.
  if (move) await windowControl("fullscreen");
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
  session.load();
  session.refresh();

  // Listening for its name is what E.V. is doing, so it is what the window
  // should show when it opens. The window is left the size it was: this is
  // the screen it was already on, not a screen it asked for.
  void api.wakeState().then((wake) => {
    if (wake?.enabled) void rest(true, false);
  });

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
  <!-- Waiting to be called: the sphere, the clock beneath it, nothing else. -->
  <main v-if="ambient" class="resting" @click="rest(false)">
    <TheOrb :live="session.listening">
      <TheAnswer />
      <!-- The one line worth having here: what to say to leave it. -->
      <p v-if="session.listening && !session.said.length" class="call">
        say “{{ session.wake?.word ?? "ev" }}”
      </p>
    </TheOrb>
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

/* The working view sits in the middle of the window rather than being
   stretched across it: a display the width of a monitor is a display nobody
   can read the two ends of at once. */
.chrome,
.grid {
  width: 100%;
  max-width: 1180px;
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

/* The sphere sizes to itself here rather than filling the column, so the
   clock sits with it instead of being pushed to the floor. Square, because a
   sphere drawn into a rectangle is drawn smaller than the room it was given. */
.resting :deep(.orb) {
  flex: 0 0 auto;
  width: min(68vh, 68vw);
  height: min(68vh, 68vw);
}

.call {
  margin: 0;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--faint);
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
