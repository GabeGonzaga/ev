<script setup lang="ts">
// The music widget: Reference 4, and a front end for the Apple Music commands.
//
// It plays nothing. Every control submits the sentence a person would have
// said -- "pause", "next", "shuffle" -- and Music does the playing, exactly as
// it does when the words are spoken. That is the whole design: this is a
// remote for something already running, not a second player.
//
// The cover is the album's own, read out of the local library. Nothing here
// fetches anything.

import { computed, ref } from "vue";
import { clock, useNowPlaying } from "../../composables/useNowPlaying";
import { type Floating, useWorkspace } from "../../stores/workspace";
import HudPane from "./HudPane.vue";

const props = withDefaults(defineProps<{ locale?: string }>(), { locale: "pt-PT" });
const emit = defineEmits<{ close: [] }>();

const { playing, pending, error, at, holding, tell } = useNowPlaying(
  () => props.locale,
);

/// Put the playhead where the finger is.
///
/// The line is a control, not a readout: press it and the song moves. The
/// position follows the pointer while it is down and the command is sent once
/// on release -- a seek per pixel would be a hundred commands to cross a
/// three-minute track, each one an Apple Event and a journal entry.
function scrub(event: PointerEvent) {
  const length = playing.value?.length ?? 0;
  if (!length || event.button !== 0) return;

  const rail = event.currentTarget as HTMLElement;
  const line = rail.getBoundingClientRect();
  rail.setPointerCapture(event.pointerId);
  holding.value = true;

  function place(x: number) {
    const part = Math.min(1, Math.max(0, (x - line.left) / line.width));
    at.value = Math.round(part * length);
  }

  function move(moved: PointerEvent) {
    place(moved.clientX);
  }

  function done(up: PointerEvent) {
    place(up.clientX);
    rail.releasePointerCapture(up.pointerId);
    rail.removeEventListener("pointermove", move);
    rail.removeEventListener("pointerup", done);
    rail.removeEventListener("pointercancel", done);
    holding.value = false;
    void tell(`seek to ${at.value}`);
  }

  place(event.clientX);
  rail.addEventListener("pointermove", move);
  rail.addEventListener("pointerup", done);
  rail.addEventListener("pointercancel", done);
}

const along = computed(() => {
  const length = playing.value?.length ?? 0;
  return length > 0 ? Math.min(100, (at.value / length) * 100) : 0;
});

/// The tag in the corner of the art, which is Reference 4's `IDLE`.
const tag = computed(() => {
  const state = playing.value?.state;
  return state === "playing" ? "play" : state === "paused" ? "hold" : "idle";
});

const repeating = computed(() => playing.value?.repeat !== "off");

/// Off, all, one, off -- the three positions a music app's repeat button
/// walks, and the reason "cycle" exists as a word. Each is the sentence a
/// person would say for it, so the button and the voice reach the same place
/// by the same route.
const ROUND: Record<string, { says: string; then: string }> = {
  off: { says: "repeat on", then: "repeat everything" },
  all: { says: "cycle", then: "repeat this track" },
  one: { says: "repeat off", then: "stop repeating" },
};

const nextRepeat = computed(() => ROUND[playing.value?.repeat ?? "off"] ?? ROUND.off);

// --- the lyrics ----------------------------------------------------------

const NAME = "apple_music";
const workspace = useWorkspace();
const reading = ref(false);
/// What shape it was before, so closing the lyrics gives that back rather
/// than leaving a tall window somebody has to resize by hand.
let wasWide: Floating | null = null;

/// A page of words wants a page's shape. Turning the window portrait is the
/// whole gesture: the cover goes to the top, the words run down the rest.
function flip() {
  const now = workspace.placement(NAME);
  if (!reading.value) {
    if (now !== "docked") wasWide = { ...now };
    reading.value = true;
    if (now !== "docked") {
      workspace.move(NAME, { ...now, width: 360, height: 560 });
    }
    return;
  }

  reading.value = false;
  if (wasWide) workspace.move(NAME, wasWide);
}

const words = computed(() => playing.value?.lyrics?.trim() ?? "");
</script>

<template>
  <HudPane
    name="apple_music"
    :pending="pending"
    :error="error"
    :empty="!playing"
    waiting="asking music..."
    :live="playing?.state === 'playing'"
    :at="{ x: 470, y: 150, width: 400, height: 168 }"
    @close="emit('close')"
  >
    <div v-if="playing" class="player" :class="{ reading }">
      <div class="art">
        <img v-if="playing.cover" :src="playing.cover" :alt="playing.album" />
        <span v-else class="nothing" />
        <span class="tag">{{ tag }}</span>
      </div>

      <div class="what">

        <p class="track" :title="playing.track">{{ playing.track || "—" }}</p>
        <p class="by" :title="playing.artist">{{ playing.artist }}</p>
        <p class="on" :title="playing.album">{{ playing.album }}</p>

        <div class="along">
          <span class="from">{{ clock(at) }}</span>
          <!-- A line, not a bar. Everything on this display is one pixel. -->
          <span class="rail" :class="{ holding }" @pointerdown="scrub">
            <span class="line">
              <span class="done" :style="{ width: along + '%' }" />
              <span class="head" :style="{ left: along + '%' }" />
            </span>
          </span>
          <span class="to">{{ clock(playing.length) }}</span>
        </div>

        <div class="transport">
          <button type="button" title="previous" @click="tell('previous')">
            <svg viewBox="0 0 24 24"><path d="M18 5v14L8 12zM6 5v14" /></svg>
          </button>
          <button
            type="button"
            :class="{ on: playing.state === 'playing' }"
            :title="playing.state === 'playing' ? 'pause' : 'play'"
            @click="tell(playing.state === 'playing' ? 'pause' : 'resume')"
          >
            <svg v-if="playing.state === 'playing'" viewBox="0 0 24 24">
              <path d="M9 5v14M15 5v14" />
            </svg>
            <svg v-else viewBox="0 0 24 24"><path d="M7 4.5v15L20 12z" /></svg>
          </button>
          <button type="button" title="next" @click="tell('next')">
            <svg viewBox="0 0 24 24"><path d="M6 5v14l10-7zM18 5v14" /></svg>
          </button>
          <button
            type="button"
            :class="{ on: playing.shuffle }"
            title="shuffle"
            @click="tell('shuffle')"
          >
            <svg viewBox="0 0 24 24">
              <path d="M3 7h4l10 10h4M3 17h4l3-3M14 10l3-3h4M17 3.5 20.5 7 17 10.5M17 13.5 20.5 17 17 20.5" />
            </svg>
          </button>
          <button
            type="button"
            :class="{ on: repeating }"
            :title="nextRepeat.then"
            @click="tell(nextRepeat.says)"
          >
            <svg viewBox="0 0 24 24">
              <path d="M4 12V9a3 3 0 0 1 3-3h13M20 12v3a3 3 0 0 1-3 3H4" />
              <path d="M17 3 20.5 6 17 9M7 15 3.5 18 7 21" />
            </svg>
            <span v-if="playing.repeat === 'one'" class="one">1</span>
          </button>
          <button
            :class="{ on: reading }"
            type="button"
            title="lyrics"
            @click="flip"
          >
            <svg viewBox="0 0 24 24">
              <path d="M4 6h16M4 10.5h11M4 15h16M4 19.5h9" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- The words, under everything, when the window has been turned for
         them. Empty is said plainly: Apple Music keeps its own lyrics to
         itself, and inventing some would be worse than none. -->
    <div v-if="playing && reading" class="lyrics">
      <p v-if="words" class="words">{{ words }}</p>
      <p v-else class="none">
        &gt; no lyrics on this track.<br />
        Music only hands over what the file itself carries, and a streamed
        track carries none.
      </p>
    </div>
  </HudPane>
</template>

<style scoped>
/* Turned for reading: the cover on top, the words down the rest of the
   window. Same components, a different axis. */
.player.reading {
  flex-direction: column;
  flex: 0 0 auto;
}

.player.reading .art {
  align-self: center;
  width: clamp(96px, 46%, 190px);
}

.player.reading .track,
.player.reading .by,
.player.reading .on {
  text-align: center;
}

.player {
  display: flex;
  gap: 14px;
  /* Fills the body, so the progress line and the transport stay on the floor
     of the window instead of following the cover's height. */
  flex: 1;
  min-height: 0;
}

/* Small, squared, with a thin edge and the blue the rest of the display is
   in -- an album cover at full saturation is the only photograph on screen
   and would win every time. */
.art {
  position: relative;
  flex: 0 0 auto;
  align-self: flex-start;
  /* Sized from the window rather than fixed: resizing the player should make
     the cover bigger, which is most of the reason anybody resizes it. */
  width: clamp(72px, 30%, 190px);
  aspect-ratio: 1;
  border: 1px solid var(--panel-border);
}

.art img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.nothing {
  display: block;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    45deg,
    rgba(63, 165, 246, 0.06) 0 6px,
    transparent 6px 12px
  );
}

.tag {
  position: absolute;
  left: 4px;
  bottom: 4px;
  padding: 1px 4px;
  background: rgba(4, 8, 16, 0.72);
  font-size: 8px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--neon-soft);
}

.what {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.track,
.by,
.on {
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track {
  font-weight: 500;
  font-size: 14px;
  color: var(--ink);
}

.by {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
}

.on {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(200, 224, 245, 0.38);
  margin-top: 1px;
}

.along {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  font-size: 9px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

/* The line stays one pixel. What grows is the room to hit it: seven pixels
   above and below, invisible, because a one-pixel control is a control nobody
   can use. */
.rail {
  flex: 1;
  padding: 7px 0;
  cursor: pointer;
  touch-action: none;
}

.line {
  position: relative;
  display: block;
  height: 1px;
  background: rgba(200, 224, 245, 0.18);
}

.done {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--neon);
  box-shadow: 0 0 6px rgba(63, 165, 246, 0.7);
}

/* The playhead. Small and dim until the line is touched, so it reads as a
   place rather than as a handle demanding to be used. */
.head {
  position: absolute;
  top: 50%;
  width: 5px;
  height: 5px;
  margin: -2.5px 0 0 -2.5px;
  border-radius: 50%;
  background: var(--neon-soft);
  opacity: 0;
  transition: opacity 0.15s;
}

.rail:hover .head,
.rail.holding .head {
  opacity: 1;
  box-shadow: 0 0 8px rgba(63, 165, 246, 0.9);
}

.transport {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 10px;
}

/* Outlined and muted, and lit only where something is actually on -- which is
   the same grammar as the dock, and the reason the one lit button is legible
   at a glance. */
.transport button {
  position: relative;
  width: 16px;
  height: 16px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s, filter 0.15s;
}

.transport svg {
  width: 100%;
  height: 100%;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.transport button:hover {
  color: #fff;
}

.transport button.on {
  color: var(--neon);
  filter: drop-shadow(0 0 5px rgba(63, 165, 246, 0.75));
}

.lyrics {
  flex: 1;
  min-height: 0;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--panel-border);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--neon-dim) transparent;
}

.lyrics::-webkit-scrollbar {
  width: 4px;
}

.lyrics::-webkit-scrollbar-thumb {
  background: var(--neon-dim);
}

.words {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 12px;
  color: var(--ink);
}

.none {
  margin: 0;
  line-height: 1.6;
  font-size: 11px;
  color: var(--muted);
}

.one {
  position: absolute;
  right: -5px;
  bottom: -4px;
  font-size: 7px;
  line-height: 1;
  color: var(--neon);
}
</style>
