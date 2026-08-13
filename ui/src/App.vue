<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { canRecordHere, dismiss } from "./api";
import FloatingWidget from "./components/FloatingWidget.vue";
import TheConsole from "./components/TheConsole.vue";
import TheDock from "./components/TheDock.vue";
import TheOrb, { type Mood } from "./components/TheOrb.vue";
import TheQuestion from "./components/TheQuestion.vue";
import TheTiles from "./components/TheTiles.vue";
import TheTranscript from "./components/TheTranscript.vue";
import { useSession } from "./stores/session";
import { useWorkspace } from "./stores/workspace";

const session = useSession();
const workspace = useWorkspace();
const typed = ref("");
const field = ref<HTMLInputElement | null>(null);
const recorder = ref<MediaRecorder | null>(null);

/// The state bus, as far as the interface is concerned: one value. The orb
/// subscribes to it and does nothing else.
const mood = computed<Mood>(() => {
  if (session.question) return "confirm";
  if (session.trouble) return "error";
  if (session.state === "listening") return "listening";
  if (session.state === "thinking") return "thinking";
  if (session.state === "speaking") return "speaking";
  return "idle";
});

/// A canvas takes the screen and docks the orb; a live feed hides it. Nothing
/// else moves it.
const surface = computed(() => workspace.surface);
const docked = computed(() => Boolean(surface.value) && surface.value !== "camera");
const hidden = computed(() => surface.value === "camera");

/// The tiles are idle-only: they go the moment anything opens.
const resting = computed(
  () => workspace.open.length === 0 && !session.said.length && !session.question,
);

/// A short line above the orb, in the system voice, that fades on its own.
const feedback = ref("");
let fading: ReturnType<typeof setTimeout> | undefined;

function announce(text: string) {
  feedback.value = text.toUpperCase();
  clearTimeout(fading);
  fading = setTimeout(() => (feedback.value = ""), 1500);
}

async function send(text?: string) {
  const line = (text ?? typed.value).trim();
  if (!line) return;
  typed.value = "";
  announce("working");
  await session.ask(line);
}

// In the app the signed host holds the microphone. In a browser the browser
// does, and asks in its own name.
async function talk() {
  if (!canRecordHere) return session.speak();

  if (recorder.value) {
    recorder.value.stop();
    recorder.value = null;
    return;
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks: Blob[] = [];
  const media = new MediaRecorder(stream);
  media.ondataavailable = (event) => chunks.push(event.data);
  media.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    await session.speak(new Blob(chunks, { type: media.mimeType }));
  };
  media.start();
  recorder.value = media;
  session.state = "listening";
}

onMounted(() => {
  session.load();
  field.value?.focus();

  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    // Nearest thing first: close what is open, then put the window away.
    if (workspace.open.length) return workspace.hide(workspace.open.at(-1)!);
    if (!session.question) void dismiss();
  });

  window.addEventListener("focus", () => field.value?.focus());
});
</script>

<template>
  <main>
    <!-- The grid is a persistent overlay: above any surface, below the orb
         and the widgets, never faded and never masked. -->
    <div class="grid-overlay" />

    <div class="stage" :class="{ docked, hidden }">
      <!-- The orb holds the centre. Everything else is placed against it:
           feedback above, speech below, tiles further below again. Nothing
           is in a column with it, because then it would not be centred. -->
      <TheOrb :mood="mood" :docked="docked" />

      <p v-if="feedback" class="feedback">{{ feedback }}</p>

      <div class="below">
        <TheQuestion />
        <TheTranscript :suppressed="workspace.isOpen('chat')" />
      </div>
    </div>

    <Transition name="fade">
      <TheTiles v-if="resting && !hidden" class="tiles-row" @pick="send($event)" />
    </Transition>

    <!-- Typing is an equivalent input, not a second interface: what is said
         here is said to E.V. exactly as if it had been spoken. -->
    <form class="line" @submit.prevent="send()">
      <input
        ref="field"
        v-model="typed"
        type="text"
        spellcheck="false"
        placeholder="say something, or type it"
      />
      <button type="button" :class="{ live: recorder }" @click="talk()">
        {{ recorder ? "[stop]" : "[speak]" }}
      </button>
    </form>

    <FloatingWidget
      v-if="workspace.isOpen('console')"
      id="console"
      tag="EV_SYS"
      :at="{ x: 60, y: 90 }"
    >
      <TheConsole />
    </FloatingWidget>

    <TheDock />
  </main>
</template>

<style scoped>
main {
  position: relative;
  height: 100vh;
  overflow: hidden;
}

.stage {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  z-index: 3;
  transition: opacity 400ms ease;
}

/* A live feed carries its own motion, and a second animated element
   competing with it reads as clutter. Gone, not dimmed. */
.hidden {
  opacity: 0;
  pointer-events: none;
}

.feedback {
  position: absolute;
  /* Half the orb, and fifty pixels of air. */
  top: calc(50% - 280px);
  margin: 0;
  font-family: var(--system);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: rgba(242, 245, 248, 0.5);
}

/* Sixty pixels under the orb, centred, and it does not push anything. */
.below {
  position: absolute;
  top: calc(50% + 290px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: min(720px, 86vw);
}

.tiles-row {
  position: fixed;
  bottom: 132px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 4;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 250ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.line {
  position: fixed;
  bottom: 66px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(520px, 72vw);
}

input {
  flex: 1;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid rgba(var(--tick), 0.22);
  border-radius: 6px;
  background: rgba(11, 13, 17, 0.6);
  font-family: var(--terminal);
  font-size: 12px;
  outline: none;
}

input:focus {
  border-color: rgba(var(--accent), 0.7);
}

input::placeholder {
  color: rgba(var(--tick), 0.4);
}

.line button {
  font-family: var(--terminal);
  font-size: 11px;
  color: rgba(var(--tick), 0.6);
}

.line button:hover,
.line .live {
  color: rgb(var(--accent));
}
</style>
