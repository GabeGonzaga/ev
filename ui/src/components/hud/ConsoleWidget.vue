<script setup lang="ts">
// The console: what was said, and a line to say more.
//
// Typing here is the same act as speaking. The text goes to the core by the
// path a transcribed utterance takes, gets routed by the same router and
// authorised by the same policy -- this panel submits a string and is told
// what happened. It executes nothing, which is the whole reason it is allowed
// to exist.
//
// `$` is the user and `>` is E.V., which is a log rather than a chat: one
// straight edge down the left, and no bubbles.

import { computed, nextTick, ref, watch } from "vue";
import { submit } from "../../api";
import { t } from "../../i18n";
import { useAssistantState } from "../../stores/assistant";
import HudPane from "./HudPane.vue";

const props = withDefaults(
  defineProps<{ locale?: string }>(),
  { locale: "pt-PT" },
);

const emit = defineEmits<{ close: [] }>();

const ev = useAssistantState();
const said = ref("");
const log = ref<HTMLDivElement | null>(null);
const trouble = ref<string | null>(null);

const busy = computed(() => ev.voice === "thinking");

async function send() {
  const text = said.value.trim();
  if (!text || busy.value) return;

  said.value = "";
  trouble.value = null;
  ev.say("user", text);
  ev.voice = "thinking";

  try {
    const answer = await submit(text, props.locale);
    const spoken = answer.spoken?.join(" ") || answer.speech || answer.outcome;
    ev.say("ev", spoken);
    if (answer.error) trouble.value = answer.error;
  } catch (error) {
    // Printed, not swallowed. A console that goes quiet when the core is not
    // there is worse than one that says the core is not there.
    trouble.value = String(error instanceof Error ? error.message : error);
  } finally {
    ev.voice = "idle";
  }
}

// Stick to the bottom while the reader is already there. Yanking somebody
// back down because a line arrived is how a log becomes unreadable at the
// moment it is worth reading.
let stuck = true;

function onScroll() {
  const box = log.value;
  if (!box) return;
  stuck = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
}

watch(
  () => ev.transcript.length,
  async () => {
    if (!stuck) return;
    await nextTick();
    const box = log.value;
    if (box) box.scrollTop = box.scrollHeight;
  },
);
</script>

<template>
  <HudPane
    name="ev_console"
    :live="busy"
    :at="{ x: 34, y: 64, width: 420, height: 320 }"
    @close="emit('close')"
  >
    <div ref="log" class="log" @scroll="onScroll">
      <p v-for="turn in ev.transcript" :key="turn.id" class="turn" :class="turn.who">
        <span class="who">{{ turn.who === "user" ? "$" : "&gt;" }}</span>
        <span class="text">{{ turn.text }}</span>
      </p>
      <p v-if="busy" class="turn ev">
        <span class="who">&gt;</span>
        <span class="text"><span class="caret" /></span>
      </p>
      <p v-if="trouble" class="turn failed">
        <span class="who">!</span>
        <span class="text">{{ trouble }}</span>
      </p>
    </div>

    <form class="line" @submit.prevent="send">
      <input
        v-model="said"
        type="text"
        :placeholder="t('console.placeholder')"
        spellcheck="false"
        autocomplete="off"
      />
    </form>

    <footer>
      <button type="button" class="act" :title="t('console.attach_hint')" disabled>
        {{ t("console.attach") }}
      </button>
      <button type="button" class="act" @click="send">{{ t("console.send") }}</button>
    </footer>
  </HudPane>
</template>

<style scoped>
.log {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--neon-dim) transparent;
}

.log::-webkit-scrollbar {
  width: 4px;
}

.log::-webkit-scrollbar-thumb {
  background: var(--neon-dim);
}

.turn {
  display: flex;
  gap: 0.7em;
  margin: 0 0 7px;
  line-height: 1.5;
}

/* One column for both marks, so the text runs down one straight edge -- which
   is the whole reason a log reads faster than a chat. */
.who {
  flex: 0 0 auto;
  width: 1.1em;
  color: var(--muted);
}

.text {
  overflow-wrap: anywhere;
}

.turn.user .text {
  color: var(--ink);
}

.turn.ev .text {
  color: var(--neon-soft);
}

.turn.failed .who,
.turn.failed .text {
  color: var(--error);
}

.line {
  border-top: 1px solid var(--panel-border);
  padding-top: 8px;
  margin-top: 6px;
}

input {
  width: 100%;
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: var(--body);
  color: var(--ink);
}

input::placeholder {
  color: rgba(200, 224, 245, 0.35);
}

input:focus {
  outline: none;
}

footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

.act {
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: 0.1em;
  color: var(--muted);
  cursor: pointer;
}

.act:hover:not(:disabled) {
  color: var(--neon-soft);
}

.act:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>
