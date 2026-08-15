<script setup lang="ts">
// The transcript: what was said, and what E.V. said back.
//
// The primary panel, and the only one anybody actually reads, which is why it
// has the middle of the display and most of its height. Everything else on
// this screen is a reading; this is the conversation.
//
// Two prefixes and no avatars, no bubbles, no timestamps down the side. `> `
// is what you typed and `EV ::` is what answered, which is the whole of the
// visual language and enough of it -- a transcript is a log, and a log that
// styles itself stops being scannable.

import { computed, nextTick, ref, watch } from "vue";
import { useFrame } from "../../composables/useFrame";
import type { Turn } from "../../stores/assistant";
import HudPane from "./HudPane.vue";

const props = defineProps<{
  turns: Turn[];
  pending?: boolean;
  error?: string | null;
}>();

const emit = defineEmits<{ revealed: [id: number] }>();

/// Characters a second. Fast enough not to be a wait, slow enough that the
/// answer arrives rather than appears -- which is the only reason to render
/// it a character at a time when the whole string is already in hand.
const RATE = 62;

const log = ref<HTMLDivElement | null>(null);

/// How much of the streaming turn has arrived. A float, so the rate does not
/// have to divide into the frame time.
const shown = ref(0);
let streaming = -1;

/// The last turn, and only if it is still arriving. Nothing before it is ever
/// partial: a transcript is not re-typed when it scrolls.
const arriving = computed(() => {
  const last = props.turns.at(-1);
  return last?.streaming ? last : null;
});

useFrame((_, delta) => {
  const turn = arriving.value;
  if (!turn) return;

  // A new one: start it from nothing rather than from where the last one had
  // got to.
  if (turn.id !== streaming) {
    streaming = turn.id;
    shown.value = 0;
  }

  if (shown.value >= turn.text.length) return;
  shown.value = Math.min(turn.text.length, shown.value + (delta * RATE) / 1000);
  // The panel knows when the text ran out; whoever owns the turn is the one
  // that can stop calling it a stream.
  if (shown.value >= turn.text.length) emit("revealed", turn.id);
});

function textOf(turn: Turn): string {
  if (turn.id !== arriving.value?.id) return turn.text;
  return turn.text.slice(0, Math.floor(shown.value));
}

// Stick to the bottom -- but only while the reader is already there. Yanking
// somebody back down because a new line arrived is how a log becomes
// unreadable at exactly the moment it is worth reading.
let stuck = true;

function onScroll() {
  const box = log.value;
  if (!box) return;
  stuck = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
}

async function toBottom() {
  if (!stuck) return;
  await nextTick();
  const box = log.value;
  if (box) box.scrollTop = box.scrollHeight;
}

watch(() => props.turns.length, toBottom);
watch(shown, toBottom);
</script>

<template>
  <HudPane
    name="conversation"
    subtitle="transcript"
    source="whisper·small"
    :pending="pending"
    :error="error"
    :empty="!turns.length"
    :live="!!arriving"
    waiting="awaiting stream"
  >
    <div ref="log" class="log" @scroll="onScroll">
      <p v-for="turn in turns" :key="turn.id" class="turn" :class="turn.who">
        <span class="who">{{ turn.who === "user" ? "&gt;" : "EV ::" }}</span>
        <span class="said">{{ textOf(turn) }}<span
          v-if="turn.id === arriving?.id"
          class="caret"
        /></span>
      </p>
    </div>
  </HudPane>
</template>

<style scoped>
.log {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
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
  margin: 0 0 9px;
  line-height: 1.55;
}

/* Fixed width so both prefixes land on the same column and the text runs in
   one straight edge down the panel -- which is the whole reason a log is
   quicker to read than a chat. */
.who {
  flex: 0 0 auto;
  min-width: 3.6em;
  color: var(--text-dim);
}

.said {
  overflow-wrap: anywhere;
}

.turn.user .said {
  color: var(--text);
}

.turn.ev .said {
  color: var(--neon);
  text-shadow: 0 0 14px rgba(61, 155, 255, 0.25);
}

.turn.ev .who {
  color: var(--neon-dim);
}
</style>
