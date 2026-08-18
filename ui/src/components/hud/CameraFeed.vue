<script setup lang="ts">
// The picture itself, wherever it is being shown.
//
// One component for the background and for the small window, because they are
// the same feed at two sizes -- and because the reticle, the label and the
// countdown are the active-state indicator, which must not be something only
// one of the two remembers to draw.

import { onBeforeUnmount, ref, watch } from "vue";

const props = defineProps<{
  stream: MediaStream | null;
  left: number;
  /// Behind everything, as the display's own background.
  behind?: boolean;
}>();

const feed = ref<HTMLVideoElement | null>(null);

watch(
  () => [props.stream, feed.value] as const,
  ([now, element]) => {
    if (!element) return;
    element.srcObject = now;
    if (now) void element.play().catch(() => undefined);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (feed.value) feed.value.srcObject = null;
});

defineExpose({ feed });
</script>

<template>
  <div class="lens" :class="{ behind }">
    <video ref="feed" class="feed" playsinline muted />

    <!-- The tint. Clear in the middle where the picture is, azure at the
         edges where the display is: it is the room the feed sits in rather
         than a colour laid over it. -->
    <span class="tint" />

    <span class="reticle" />
    <span class="bracket tl" />
    <span class="bracket tr" />
    <span class="bracket bl" />
    <span class="bracket br" />

    <span class="label">cam_01 // live</span>
    <span v-if="left > 0" class="left">{{ left }}s</span>
  </div>
</template>

<style scoped>
.lens {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  /* Cooled and dimmed. A camera feed at full colour is the brightest thing
     that has ever been on this display and would own it. */
  filter: saturate(0.55) contrast(1.02) brightness(0.72);
}

/* As the background: further back still, so the grid drawn over it reads as
   the instrument standing in front of the room rather than as a pattern
   printed on the picture. */
.behind .feed {
  filter: saturate(0.4) contrast(1) brightness(0.42);
  opacity: 0.75;
}

.tint {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(
      118% 118% at 50% 50%,
      transparent 42%,
      rgba(63, 165, 246, 0.16) 78%,
      rgba(13, 20, 33, 0.72) 100%
    );
}

.behind .tint {
  background:
    radial-gradient(
      120% 120% at 50% 48%,
      transparent 30%,
      rgba(63, 165, 246, 0.2) 72%,
      rgba(13, 20, 33, 0.88) 100%
    );
}

/* A thin cross at the centre, quiet enough to look past. */
.reticle {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 26px;
  height: 26px;
  margin: -13px 0 0 -13px;
  background:
    linear-gradient(var(--neon), var(--neon)) 50% 0 / 1px 100% no-repeat,
    linear-gradient(var(--neon), var(--neon)) 0 50% / 100% 1px no-repeat;
  opacity: 0.28;
}

.bracket {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 0 solid var(--neon-dim);
}

.bracket.tl {
  top: 8px;
  left: 8px;
  border-top-width: 1px;
  border-left-width: 1px;
}

.bracket.tr {
  top: 8px;
  right: 8px;
  border-top-width: 1px;
  border-right-width: 1px;
}

.bracket.bl {
  bottom: 8px;
  left: 8px;
  border-bottom-width: 1px;
  border-left-width: 1px;
}

.bracket.br {
  bottom: 8px;
  right: 8px;
  border-bottom-width: 1px;
  border-right-width: 1px;
}

/* The active state, said in words, for as long as the lens is open. */
.label,
.left {
  position: absolute;
  bottom: 10px;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--neon-soft);
}

.label {
  left: 30px;
}

.left {
  right: 30px;
  color: var(--muted);
}

.behind .label {
  left: 40px;
  bottom: 30px;
}

.behind .left {
  right: 40px;
  bottom: 30px;
}
</style>
