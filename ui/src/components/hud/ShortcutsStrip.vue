<script setup lang="ts">
// The shortcuts strip, and the form that adds to it.
//
// A shortcut is a line of text, not a URL. Clicking one submits `open
// github.com` to the core exactly as if it had been typed, and the core
// decides what that means -- which is why this can exist at all: a strip that
// assembled URLs and opened them itself would be a browser with opinions,
// and this is a button that says a sentence.

import { ref } from "vue";
import { submit } from "../../api";
import { useAssistantState } from "../../stores/assistant";
import { useShortcuts } from "../../stores/shortcuts";
import HudPane from "./HudPane.vue";
import { t } from "../../i18n";

const props = withDefaults(
  defineProps<{ adding?: boolean; locale?: string }>(),
  { adding: false, locale: "en" },
);

const emit = defineEmits<{ close: []; done: [] }>();

const ev = useAssistantState();
const shortcuts = useShortcuts();
const label = ref("");
const says = ref("");

async function run(text: string) {
  ev.say("user", text);
  try {
    const answer = await submit(text, props.locale);
    ev.say("ev", answer.spoken?.join(" ") || answer.speech || answer.outcome);
  } catch (error) {
    ev.say("ev", String(error instanceof Error ? error.message : error));
  }
}

function keep() {
  shortcuts.add(label.value, says.value);
  label.value = "";
  says.value = "";
  emit("done");
}
</script>

<template>
  <HudPane
    v-if="!adding"
    name="shortcuts"
    :at="{ x: 34, y: 404, width: 300, height: 150 }"
    @close="emit('close')"
  >
    <div class="strip">
      <button
        v-for="one in shortcuts.saved"
        :key="one.id"
        class="one"
        type="button"
        :title="one.says"
        @click="run(one.says)"
      >
        {{ one.label }}
        <span class="drop" :title="t('shortcuts.forget')" @click.stop="shortcuts.forget(one.id)">×</span>
      </button>
      <p v-if="!shortcuts.saved.length" class="none">&gt; {{ t("shortcuts.empty") }}</p>
    </div>
  </HudPane>

  <!-- The add form. A frame, not a window: nothing to move, and no rounded
       modal anywhere near it. -->
  <HudPane
    v-else
    name="add_shortcut"
    :movable="false"
    class="adding"
    @close="emit('close')"
  >
    <form class="form" @submit.prevent="keep">
      <label>
        <span>{{ t("shortcuts.label") }}</span>
        <input
          v-model="label"
          spellcheck="false"
          autocomplete="off"
          :placeholder="t('shortcuts.label_hint')"
        />
      </label>
      <label>
        <span>{{ t("shortcuts.says") }}</span>
        <input
          v-model="says"
          spellcheck="false"
          autocomplete="off"
          :placeholder="t('shortcuts.says_hint')"
        />
      </label>
      <button class="keep" type="submit">{{ t("shortcuts.save") }}</button>
    </form>
  </HudPane>
</template>

<style scoped>
.strip {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  overflow-y: auto;
}

.one {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 1px solid var(--panel-border);
  background: none;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--muted);
  cursor: pointer;
}

.one:hover {
  color: var(--neon-soft);
  border-color: rgba(58, 160, 255, 0.6);
}

.drop {
  color: rgba(200, 224, 245, 0.35);
}

.drop:hover {
  color: var(--error);
}

.none {
  margin: 0;
  color: var(--muted);
}

/* Centred over the display, because it was asked for rather than left open. */
.adding {
  position: fixed;
  left: 50%;
  bottom: 96px;
  width: 300px;
  transform: translateX(-50%);
  z-index: 30;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: var(--label-track);
  text-transform: uppercase;
  color: var(--muted);
}

label span {
  width: 44px;
}

input {
  flex: 1;
  min-width: 0;
  padding: 3px 6px;
  border: 1px solid var(--panel-border);
  background: rgba(4, 10, 18, 0.5);
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink);
}

input:focus {
  outline: none;
  border-color: rgba(58, 160, 255, 0.7);
}

.keep {
  align-self: flex-end;
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: 0.1em;
  color: var(--neon-soft);
  cursor: pointer;
}
</style>
