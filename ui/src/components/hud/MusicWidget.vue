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

import { computed } from "vue";
import { clock, useNowPlaying } from "../../composables/useNowPlaying";
import HudPane from "./HudPane.vue";

const props = withDefaults(defineProps<{ locale?: string }>(), { locale: "pt-PT" });
const emit = defineEmits<{ close: [] }>();

const { playing, pending, error, at, tell } = useNowPlaying(() => props.locale);

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
    <div v-if="playing" class="player">
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
          <span class="rail"><span class="done" :style="{ width: along + '%' }" /></span>
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
            :title="playing.repeat === 'one' ? 'repeating this track' : 'repeat'"
            @click="tell('repeat')"
          >
            <svg viewBox="0 0 24 24">
              <path d="M4 12V9a3 3 0 0 1 3-3h13M20 12v3a3 3 0 0 1-3 3H4" />
              <path d="M17 3 20.5 6 17 9M7 15 3.5 18 7 21" />
            </svg>
            <span v-if="playing.repeat === 'one'" class="one">1</span>
          </button>
        </div>
      </div>
    </div>
  </HudPane>
</template>

<style scoped>
.player {
  display: flex;
  gap: 14px;
  min-height: 0;
}

/* Small, squared, with a thin edge and the blue the rest of the display is
   in -- an album cover at full saturation is the only photograph on screen
   and would win every time. */
.art {
  position: relative;
  flex: 0 0 auto;
  width: 96px;
  height: 96px;
  border: 1px solid var(--panel-border);
}

.art img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  filter: contrast(1.05) brightness(0.9);
}

/* The duotone. `color` takes hue and saturation from this and leaves the
   cover's own luminance alone, which is what keeps it a photograph rather
   than a blue rectangle -- and it is the only image on a screen that is
   otherwise one hue. */
.art::after {
  content: "";
  position: absolute;
  inset: 0;
  background: rgba(58, 160, 255, 0.55);
  mix-blend-mode: color;
  pointer-events: none;
}

.nothing {
  display: block;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    45deg,
    rgba(58, 160, 255, 0.06) 0 6px,
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

.rail {
  position: relative;
  flex: 1;
  height: 1px;
  background: rgba(200, 224, 245, 0.18);
}

.done {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--neon);
  box-shadow: 0 0 6px rgba(58, 160, 255, 0.7);
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
  filter: drop-shadow(0 0 5px rgba(58, 160, 255, 0.75));
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
