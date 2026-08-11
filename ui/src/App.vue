<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useSession } from "./stores/session";

const session = useSession();
const typed = ref("");

onMounted(() => session.refresh());

async function send() {
  const text = typed.value;
  typed.value = "";
  await session.ask(text);
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
      <button type="button" :disabled="session.state !== 'idle'" @click="session.speak()">
        Speak
      </button>
    </form>

    <!-- What E.V. heard, shown even when it is right: being misheard should be
         visible in the words rather than inferred from the wrong action. -->
    <p v-if="session.heard" class="heard">heard: {{ session.heard }}</p>
    <p v-for="line in session.said" :key="line" class="said">{{ line }}</p>
    <p v-if="session.trouble" class="trouble">{{ session.trouble }}</p>

    <ul class="history">
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
.history { list-style: none; margin: 0; padding: 0; overflow-y: auto; flex: 1; }
.history li { display: flex; gap: 8px; padding: 3px 0; border-top: 1px solid #2c2c2e; }
.ok { color: #30d158; }
.failed { color: #ff453a; }
.tool { color: #64d2ff; }
.detail { color: #8e8e93; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
