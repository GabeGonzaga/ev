<script setup lang="ts">
import { onMounted, ref } from "vue";
import { canBindKeys, canRecordHere } from "./api";
import { useSession } from "./stores/session";

const session = useSession();
const typed = ref("");
const recorder = ref<MediaRecorder | null>(null);

onMounted(() => {
  session.refresh();
  session.load();
});

// Recorded as it is typed, so "Cmd+Shift+Space" is one gesture rather than
// something to spell. The app answers whether it could take the key.
function record(event: KeyboardEvent) {
  event.preventDefault();
  if (["Meta", "Shift", "Alt", "Control"].includes(event.key)) return;

  const parts = [];
  if (event.metaKey) parts.push("CmdOrCtrl");
  if (event.ctrlKey && !event.metaKey) parts.push("Ctrl");
  if (event.altKey) parts.push("Alt");
  if (event.shiftKey) parts.push("Shift");
  parts.push(event.code.replace(/^Key|^Digit/, ""));

  if (parts.length < 2) return;
  session.bind(parts.join("+"));
}

// Typing is faster than a round trip to SQLite, so the last keystroke wins
// rather than every one of them queueing a query.
let pending: ReturnType<typeof setTimeout> | undefined;

function find(text: string) {
  session.search = text;
  clearTimeout(pending);
  pending = setTimeout(() => session.refresh(), 150);
}

async function peek() {
  const text = typed.value.trim();
  typed.value = "";
  await session.look(text || null);
}

async function send() {
  const text = typed.value;
  typed.value = "";
  await session.ask(text);
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
</script>

<template>
  <main>
    <header>
      <span class="dot" :class="session.state" />
      <span class="state">{{ session.state }}</span>
      <select :value="session.locale" @change="session.choose(($event.target as HTMLSelectElement).value)">
        <option value="pt-PT">pt-PT</option>
        <option value="en">en</option>
      </select>
    </header>

    <form @submit.prevent="send">
      <input v-model="typed" placeholder="abre example.com" autofocus />
      <button type="submit" :disabled="session.state !== 'idle'">Send</button>
      <button
        type="button"
        :disabled="session.state !== 'idle' && !recorder"
        @click="talk()"
      >
        {{ recorder ? "Stop" : "Speak" }}
      </button>
      <!-- One frame, then the camera goes off again. What is typed goes with
           it as the question; empty means "describe it". -->
      <button
        type="button"
        :disabled="session.state !== 'idle'"
        @click="peek()"
      >
        Look
      </button>
    </form>

    <!-- What E.V. heard, shown even when it is right: being misheard should be
         visible in the words rather than inferred from the wrong action. -->
    <!-- A question, not a notice: nothing has run, and it will not until this
         is answered. Declining is what happens if the page simply closes. -->
    <div v-if="session.question" class="asking">
      <span>
        <strong>{{ session.question.tool }}</strong>
        <em>{{ session.question.risk }}</em>
        {{ JSON.stringify(session.question.arguments) }}
      </span>
      <button type="button" @click="session.answer(true)">Run it</button>
      <button type="button" @click="session.answer(false)">Cancel</button>
    </div>

    <!-- Invariant 8, the visible half. macOS lights its own indicator; this
         one says which application did it, and goes out with the camera. -->
    <p v-if="session.camera" class="camera">● the camera is on</p>

    <p v-if="session.heard" class="heard">heard: {{ session.heard }}</p>
    <p v-for="line in session.said" :key="line" class="said">{{ line }}</p>
    <p v-if="session.trouble" class="trouble">{{ session.trouble }}</p>

    <!-- Hold this anywhere on the machine to talk. It is a key combination,
         not an event tap, so E.V. hears this and nothing else. -->
    <p v-if="canBindKeys" class="shortcut">
      <span>Hold to talk:</span>
      <input
        readonly
        :value="session.shortcut"
        placeholder="click and press a combination"
        @keydown="record"
      />
      <em v-if="session.shortcutTrouble">{{ session.shortcutTrouble }}</em>
    </p>

    <!-- The same search the CLI does, over the same journal: the page sends a
         word, the core matches it. -->
    <input
      class="find"
      :value="session.search"
      placeholder="search what E.V. has done"
      @input="find(($event.target as HTMLInputElement).value)"
    />

    <ul class="history">
      <li v-if="!session.entries.length && session.search" class="empty">
        nothing matches "{{ session.search }}"
      </li>
      <li v-for="entry in session.entries" :key="entry.id">
        <span :class="entry.ok ? 'ok' : 'failed'">{{ entry.ok ? "✓" : "✕" }}</span>
        <span class="tool">{{ entry.tool }}</span>
        <span class="detail">{{ entry.speech ?? entry.error_message ?? "" }}</span>
      </li>
    </ul>
  </main>
</template>

<style scoped>
main {
  font: 13px/1.5 -apple-system, system-ui, sans-serif;
  padding: 14px;
  color: #f2f2f7;
  background: #1c1c1e;
  height: 100vh;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
header { display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #48484a; }
.dot.listening { background: #ff453a; }
.dot.thinking { background: #ffd60a; }
.state { color: #8e8e93; flex: 1; }
select, input, button {
  font: inherit; color: inherit; background: #2c2c2e;
  border: 1px solid #3a3a3c; border-radius: 6px; padding: 5px 8px;
}
form { display: flex; gap: 6px; }
input { flex: 1; }
button:disabled { opacity: 0.4; }
.heard { color: #8e8e93; margin: 0; }
.said { margin: 0; }
.trouble { color: #ff9f0a; margin: 0; }
.asking {
  display: flex; align-items: center; gap: 8px;
  background: #3a2a00; border: 1px solid #ffd60a; border-radius: 6px; padding: 8px;
}
.asking span { flex: 1; }
.asking em { color: #ffd60a; font-style: normal; margin: 0 6px; }
.camera { color: #ff453a; margin: 6px 0 0; font-weight: 600; }
.shortcut { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.shortcut input { flex: 1; }
.shortcut em { color: #ff9f0a; font-style: normal; }
.find { width: 100%; margin-top: 8px; }
.empty { color: #8e8e93; border-top: 1px solid #2c2c2e; padding: 3px 0; }
.history { list-style: none; margin: 0; padding: 0; overflow-y: auto; flex: 1; }
.history li { display: flex; gap: 8px; padding: 3px 0; border-top: 1px solid #2c2c2e; }
.ok { color: #30d158; }
.failed { color: #ff453a; }
.tool { color: #64d2ff; }
.detail { color: #8e8e93; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
