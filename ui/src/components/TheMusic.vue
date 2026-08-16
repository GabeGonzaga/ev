<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import * as api from "../api";
import { useSession } from "../stores/session";

/// The player: what Music is on, and the buttons to move it.
///
/// The widget reads now-playing to fill itself, and its buttons submit the
/// same utterances the voice does -- `Registry.call()` still authorises every
/// one (invariant 6). It never speaks to Apple Music itself; it asks the core,
/// which drives the local player through the AppleScript adapter that already
/// exists. Nothing here reaches a service on the internet (invariant 10).
const session = useSession();

const now = ref<api.NowPlaying | null>(null);
let poll = 0;

/// Poll while the window is open. A second is enough for a progress bar and
/// cheap next to what it shows; the interval is cleared the moment the widget
/// is closed, so a shut player costs nothing.
async function read() {
  try {
    now.value = await api.nowPlaying();
  } catch {
    // The read may not be wired on this surface yet. A resting player is a
    // truer answer than an error the user can do nothing about.
    now.value = null;
  }
}

onMounted(() => {
  void read();
  poll = window.setInterval(read, 1000);
});
onUnmounted(() => window.clearInterval(poll));

const playing = computed(() => now.value?.state === "playing");

/// What the art corner reads: the state, in a word. Idle when there is
/// nothing, so an empty player still says something.
const tag = computed(() => (now.value?.state ?? "idle").toUpperCase());

const title = computed(() => now.value?.title || "Nothing playing");
const artist = computed(() => now.value?.artist || "—");
const album = computed(() => now.value?.album || "");

const position = computed(() => now.value?.position ?? 0);
const duration = computed(() => now.value?.duration ?? 0);
const progress = computed(() =>
  duration.value > 0 ? Math.min(100, (position.value / duration.value) * 100) : 0,
);

function clock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/// The words the router already answers to, in the session's language. A
/// button is a shortcut to a spoken command, not a new way in.
const SAY = {
  "pt-PT": { resume: "retoma a música", pause: "pausa", next: "próxima música", previous: "música anterior" },
  en: { resume: "resume music", pause: "pause", next: "next track", previous: "previous track" },
} as const;

const lang = computed<"pt-PT" | "en">(() => (session.locale === "pt-PT" ? "pt-PT" : "en"));
const busy = computed(() => session.state !== "idle");

function command(kind: "resume" | "pause" | "next" | "previous") {
  if (busy.value) return;
  void session.ask(SAY[lang.value][kind]);
}

function toggle() {
  command(playing.value ? "pause" : "resume");
}
</script>

<template>
  <div class="player">
    <div class="top">
      <!-- The cover, when the library gives one; otherwise a tile drawn in
           the HUD's own hand, so a missing image is never a broken one. -->
      <div class="art" :class="{ lit: playing }">
        <img v-if="now?.artwork" :src="now.artwork" alt="" />
        <svg v-else viewBox="0 0 24 24" aria-hidden="true" class="glyph">
          <path d="M9 18V5l10-2v13" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="16" cy="16" r="3" />
        </svg>
        <span class="state">{{ tag }}</span>
      </div>

      <div class="meta">
        <p class="title" :title="title">{{ title }}</p>
        <p class="artist">{{ artist }}</p>
        <p v-if="album" class="album">{{ album }}</p>
      </div>
    </div>

    <div class="scrub">
      <span class="t">{{ clock(position) }}</span>
      <div class="track"><span class="fill" :style="{ width: progress + '%' }" /></div>
      <span class="t">{{ clock(duration) }}</span>
    </div>

    <div class="transport">
      <button type="button" title="previous" :disabled="busy" @click="command('previous')">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M18 6v12L9 12zM6 6v12" />
        </svg>
      </button>

      <button
        type="button"
        class="play"
        :title="playing ? 'pause' : 'play'"
        :disabled="busy"
        @click="toggle"
      >
        <svg v-if="playing" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 5h3v14H8zM13 5h3v14h-3z" />
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 5l12 7-12 7z" />
        </svg>
      </button>

      <button type="button" title="next" :disabled="busy" @click="command('next')">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 6v12l9-6zM18 6v12" />
        </svg>
      </button>

      <button type="button" class="loop" title="repeat" disabled>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M17 2l4 4-4 4" />
          <path d="M3 12V9a3 3 0 013-3h15" />
          <path d="M7 22l-4-4 4-4" />
          <path d="M21 12v3a3 3 0 01-3 3H3" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.player {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.top {
  display: flex;
  gap: 12px;
  align-items: stretch;
  min-width: 0;
}

/* The square cover on the left, with the state written into its corner the
   way the design tags it. Lit while it plays. */
.art {
  position: relative;
  flex: 0 0 auto;
  width: 84px;
  height: 84px;
  border: 1px solid var(--panel-edge);
  border-radius: 2px;
  background: rgba(var(--accent), 0.06);
  display: grid;
  place-items: center;
  overflow: hidden;
}

.art.lit {
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.art img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.glyph {
  width: 34px;
  height: 34px;
  fill: none;
  stroke: rgba(var(--accent), 0.55);
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.state {
  position: absolute;
  left: 4px;
  bottom: 4px;
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.14em;
  padding: 1px 4px;
  color: var(--ink);
  background: rgba(4, 10, 18, 0.72);
  border: 1px solid var(--line);
  border-radius: 1px;
}

.meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  justify-content: center;
}

.title {
  margin: 0;
  font-family: var(--wordmark-font);
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 0 14px rgba(var(--accent), 0.4);
}

.artist {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.album {
  margin: 0;
  font-size: 11px;
  color: var(--faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scrub {
  display: flex;
  align-items: center;
  gap: 8px;
}

.t {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--faint);
  flex: 0 0 auto;
}

.track {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  background: rgba(var(--accent), 0.16);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  background: rgb(var(--accent));
  box-shadow: var(--glow);
  transition: width 0.4s linear;
}

.transport {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.transport button {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--field);
  color: var(--muted);
  transition: color 0.15s, border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}

.transport button:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.transport button:disabled {
  opacity: 0.4;
}

/* The play button is the lit one, the way the design fills it. */
.play {
  color: var(--ink) !important;
  border-color: var(--panel-lit) !important;
  background: rgba(var(--accent), 0.16) !important;
  box-shadow: var(--glow);
}

.loop {
  /* Repeat is shown but not yet wired: no tool sets Music's repeat mode, so
     the button reads as present-but-off rather than pretending to work. */
  opacity: 0.4;
}

.transport svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
  stroke: currentColor;
  stroke-width: 0.5;
}

.loop svg {
  fill: none;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
