<script setup lang="ts">
import { computed } from "vue";
import { canBindKeys } from "../api";
import { useSession } from "../stores/session";

const session = useSession();
const emit = defineEmits<{ pick: [string] }>();

/// What E.V. can be asked, in the language it is set to. Real phrasings, not
/// a feature list: the fastest way to learn what a thing understands is to
/// see a sentence that works.
const EXAMPLES: Record<string, string[]> = {
  "pt-PT": [
    "abre o github",
    "toca o álbum Blonde",
    "lembra-me de comprar pão",
    "cria uma nota chamada Compras",
  ],
  en: [
    "open github",
    "play the album Blonde",
    "remind me to call the dentist",
    "make a note called Shopping",
  ],
};

const examples = computed(() => EXAMPLES[session.locale] ?? EXAMPLES.en);

/// ⌘⇧Space rather than CmdOrCtrl+Shift+Space: the keys as they are printed.
const key = computed(() =>
  session.shortcut
    .split("+")
    .map(
      (part) =>
        ({ CmdOrCtrl: "⌘", Cmd: "⌘", Ctrl: "⌃", Alt: "⌥", Shift: "⇧" })[part] ??
        part,
    )
    .join(""),
);
</script>

<template>
  <div class="hints">
    <p v-if="canBindKeys && session.shortcut" class="key">
      Hold <kbd>{{ key }}</kbd> anywhere to talk
    </p>
    <ul>
      <li v-for="example in examples" :key="example">
        <button type="button" @click="emit('pick', example)">
          {{ example }}
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.hints {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 2px;
}

.key {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

kbd {
  font-family: var(--font);
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--raised);
  border: 1px solid var(--line);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

button {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--field);
  font-size: 12px;
  color: var(--muted);
  transition: color 0.15s, border-color 0.15s;
}

button:hover {
  color: var(--text);
  border-color: var(--accent);
}
</style>
