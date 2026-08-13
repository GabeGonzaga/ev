<script setup lang="ts">
import { nextTick, ref } from "vue";
import { useSession } from "../stores/session";

const session = useSession();
const typed = ref("");
const busy = ref(false);
const scrollback = ref<{ kind: "said" | "back" | "note"; text: string }[]>([
  { kind: "note", text: "E.V. console. `help` for what it knows." },
]);
const log = ref<HTMLElement | null>(null);
const past: string[] = [];
let walked = 0;

/// Not a shell, and it says so when asked. Every line here is either one of
/// E.V.'s own verbs or an utterance, and an utterance goes down the same road
/// as one typed anywhere else: the router, the policy, Registry.call().
const HELP = [
  "help              what this knows",
  "clear             empty the scrollback",
  "trail [text]      the journal, or a search of it",
  "who               what E.V. is, and what it is doing",
  "<anything else>   said to E.V. as if spoken",
];

function write(kind: "said" | "back" | "note", text: string) {
  scrollback.value.push({ kind, text });
  void nextTick(() => log.value?.scrollTo({ top: log.value.scrollHeight }));
}

async function run() {
  const line = typed.value.trim();
  if (!line || busy.value) return;
  typed.value = "";
  past.push(line);
  walked = past.length;
  write("said", line);

  const [verb, ...rest] = line.split(/\s+/);
  const argument = rest.join(" ");

  if (verb === "help") return HELP.forEach((entry) => write("note", entry));
  if (verb === "clear") return void (scrollback.value = []);

  if (verb === "who") {
    write("note", `state ${session.state} · language ${session.locale}`);
    if (session.shortcut) write("note", `hold ${session.shortcut} to talk`);
    return;
  }

  if (verb === "trail") {
    session.search = argument;
    await session.refresh();
    if (!session.entries.length) return write("note", "nothing");
    return session.entries
      .slice(0, 12)
      .forEach((entry) =>
        write("back", `${entry.ok ? "▸" : "✕"} ${entry.tool}  ${entry.speech ?? ""}`),
      );
  }

  busy.value = true;
  try {
    await session.ask(line);
    // Whatever the turn said is already in the store; the console repeats it
    // where it was typed, because a prompt that answers somewhere else is not
    // a prompt.
    session.said.forEach((said) => write("back", said));
    if (session.trouble) write("back", session.trouble);
  } finally {
    busy.value = false;
  }
}

/// Up and down walk what was typed before, as a terminal does.
function walk(step: number) {
  if (!past.length) return;
  walked = Math.min(past.length, Math.max(0, walked + step));
  typed.value = past[walked] ?? "";
}
</script>

<template>
  <div class="console">
    <div ref="log" class="log">
      <p v-for="(line, index) in scrollback" :key="index" :class="line.kind">
        <span v-if="line.kind === 'said'" class="caret">›</span>{{ line.text }}
      </p>
    </div>

    <form class="prompt" @submit.prevent="run()">
      <span class="caret">›</span>
      <input
        v-model="typed"
        type="text"
        spellcheck="false"
        :placeholder="busy ? 'working' : 'help'"
        :disabled="busy"
        @keydown.up.prevent="walk(-1)"
        @keydown.down.prevent="walk(1)"
      />
    </form>
  </div>
</template>

<style scoped>
.console {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
  flex: 1;
  font-family: var(--mono);
  font-size: 11.5px;
}

.log {
  flex: 1;
  min-height: 60px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.said {
  color: var(--ink);
}

.back {
  color: var(--text);
}

.note {
  color: var(--faint);
}

.caret {
  color: rgb(var(--accent));
  margin-right: 6px;
}

.prompt {
  display: flex;
  align-items: center;
  border-top: 1px solid var(--line);
  padding-top: 6px;
}

input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: none;
  outline: none;
  font: inherit;
  color: var(--text);
}

input::placeholder {
  color: var(--faint);
}
</style>
