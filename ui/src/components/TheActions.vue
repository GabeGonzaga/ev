<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { useSession } from "../stores/session";

/// The quick row under the orb: the two or three things reached often enough
/// to earn a button, plus a way to open a site by hand.
///
/// Not a second way to run tools. Every button here submits an utterance the
/// core routes, exactly as if it had been typed or spoken -- `Registry.call()`
/// is still the only thing that authorises anything (invariant 6). The camera
/// takes the one-frame path the composer already uses; nothing is held open.
const session = useSession();

/// The phrasings the router already knows, in the language the session is set
/// to -- the same real sentences the hints offer, so a button is a shortcut to
/// a working utterance rather than a new grammar to get right.
const PHRASES = {
  music: { "pt-PT": "abre o Music", en: "open Music" },
  openPrefix: { "pt-PT": "abre ", en: "open " },
} as const;

type Lang = "pt-PT" | "en";
const lang = computed<Lang>(() => (session.locale === "pt-PT" ? "pt-PT" : "en"));

/// A turn at a time: while one is running, the row is quiet rather than
/// stacking a second request on top of it.
const busy = computed(() => session.state !== "idle");

const linking = ref(false);
const url = ref("");
const field = ref<HTMLInputElement | null>(null);

function music() {
  if (busy.value) return;
  void session.ask(PHRASES.music[lang.value]);
}

function camera() {
  if (busy.value) return;
  void session.look();
}

async function toggleLink() {
  linking.value = !linking.value;
  if (linking.value) {
    await nextTick();
    field.value?.focus();
  }
}

function openLink() {
  const site = url.value.trim();
  if (!site || busy.value) return;
  // Generated text may never select a target (the two model paths); this is
  // not generated -- it is what the user typed, submitted as an utterance for
  // the router to resolve into the browser adapter, which opens it in the
  // user's own browser (invariant 10: an explicit action, not a fetch).
  void session.ask(PHRASES.openPrefix[lang.value] + site);
  url.value = "";
  linking.value = false;
}
</script>

<template>
  <div class="actions" :class="{ busy }">
    <button type="button" title="music" :disabled="busy" @click="music">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 18V5l10-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="16" cy="16" r="3" />
      </svg>
      <span>Music</span>
    </button>

    <button type="button" title="camera" :disabled="busy" @click="camera">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 8h4l2-3h6l2 3h4v11H3z" />
        <circle cx="12" cy="13" r="3.5" />
      </svg>
      <span>Camera</span>
    </button>

    <button
      type="button"
      title="open a site"
      class="add"
      :class="{ open: linking }"
      @click="toggleLink"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5v14M5 12h14" />
      </svg>
      <span>Link</span>
    </button>

    <!-- The one action that needs a word: a site to open. Enter submits it as
         an utterance; Escape gives up on it without leaving the field behind. -->
    <form v-if="linking" class="entry" @submit.prevent="openLink">
      <input
        ref="field"
        v-model="url"
        type="text"
        inputmode="url"
        placeholder="github.com"
        spellcheck="false"
        autocapitalize="off"
        @keydown.esc="linking = false"
      />
    </form>
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 2px 0 6px;
}

button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px 5px 9px;
  border-radius: 2px;
  border: 1px solid var(--line);
  background: var(--field);
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.02em;
  transition: color 0.15s, border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}

button:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

button:disabled {
  opacity: 0.4;
}

svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* The add button reads as the odd one out: it opens a field rather than
   running something, so it is drawn as a plus and lights when it is open. */
.add.open {
  color: var(--text);
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.entry {
  flex-basis: 100%;
  display: flex;
  justify-content: center;
}

input {
  width: min(280px, 80%);
  padding: 5px 10px;
  border-radius: 2px;
  border: 1px solid var(--panel-lit);
  background: var(--field);
  color: var(--text);
  font-family: var(--mono);
  font-size: 12px;
  box-shadow: var(--glow);
}

input::placeholder {
  color: var(--faint);
}
</style>
