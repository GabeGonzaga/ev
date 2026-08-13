<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import { canRecordHere } from "../api";
import { useSession } from "../stores/session";

const session = useSession();
const typed = ref("");
const field = ref<HTMLInputElement | null>(null);
const recorder = ref<MediaRecorder | null>(null);

/// The panel is summoned to be typed into, so it is typed into. Re-focused
/// when a turn ends too: the next thing someone does is ask again.
function take() {
  void nextTick(() => field.value?.focus());
}

onMounted(take);
watch(
  () => session.state,
  (now) => now === "idle" && take(),
);

/// A suggestion, put in the field rather than run: it is an example to edit,
/// and a panel that acts on a click nobody meant is a panel people stop
/// clicking in.
function suggest(text: string) {
  typed.value = text;
  take();
}

defineExpose({ take, suggest });

async function send() {
  const text = typed.value.trim();
  if (!text) return;
  typed.value = "";
  await session.ask(text);
}

async function look() {
  const text = typed.value.trim();
  typed.value = "";
  await session.look(text || null);
}

// In the app the signed host holds the microphone. In a browser the browser
// does, and asks in its own name -- E.V. never pretends to hold a permission
// it was not given.
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

function onKey(event: KeyboardEvent) {
  if (event.key !== "Enter") return;
  event.preventDefault();
  if (event.metaKey) return void look();
  if (event.altKey) return void talk();
  void send();
}
</script>

<template>
  <div class="composer">
    <input
      ref="field"
      v-model="typed"
      class="ask"
      type="text"
      autofocus
      spellcheck="false"
      :placeholder="session.locale === 'pt-PT' ? 'abre o github' : 'open github'"
      :disabled="session.state === 'thinking'"
      @keydown="onKey"
    />

    <!-- The keys, not just the buttons: this is a panel that opens under the
         hands, and reaching for a mouse is the slow path. -->
    <div class="keys">
      <button type="button" :disabled="!typed.trim()" @click="send()">
        <kbd>⏎</kbd> send
      </button>
      <button type="button" :class="{ live: recorder }" @click="talk()">
        <kbd>⌥⏎</kbd> {{ recorder ? "stop" : "speak" }}
      </button>
      <button type="button" :disabled="session.state !== 'idle'" @click="look()">
        <kbd>⌘⏎</kbd> look
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ask {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  font-size: 19px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--field);
  transition: border-color 0.15s;
}

.ask::placeholder {
  color: var(--faint);
}

.ask:focus {
  outline: none;
  border-color: var(--accent);
}

.keys {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.keys button {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 6px;
  color: var(--muted);
  font-size: 12px;
  transition: background 0.15s, color 0.15s;
}

.keys button:hover:not(:disabled) {
  background: var(--raised);
  color: var(--text);
}

.keys button:disabled {
  opacity: 0.4;
  cursor: default;
}

.keys .live {
  color: var(--live);
}

kbd {
  font-family: var(--font);
  font-size: 11px;
  color: var(--faint);
}
</style>
