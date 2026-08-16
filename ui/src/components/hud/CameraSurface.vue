<script setup lang="ts">
// The camera surface: the feed in the middle, the core shrunk to a badge.
//
// A surface, not a capability. The one-frame path is unchanged -- the browser
// owns the lens here exactly as it owns the microphone, `getUserMedia` asks in
// the browser's own name, and in the app the signed host owns it and the
// window never sees a frame at all. What this adds is somewhere to look while
// deciding to take one.
//
// Invariant 8, in the three places it actually bites:
//   * the lens says so while it is open -- the dock lights, and the reticle is
//     on screen the whole time
//   * the session has an end. Two minutes and it closes itself, because a
//     camera left on by a forgotten window is the failure mode that matters
//   * nothing is kept. There is no recording, no snapshot, and the stream is
//     stopped on the way out.

import { onBeforeUnmount, onMounted, ref } from "vue";
import { capturesHere, look } from "../../api";

const props = withDefaults(defineProps<{ locale?: string }>(), { locale: "pt-PT" });
const emit = defineEmits<{ close: []; live: [on: boolean]; said: [text: string] }>();

const feed = ref<HTMLVideoElement | null>(null);
const trouble = ref<string | null>(null);
const asking = ref(false);
/// Seconds left of the session. Shown, because a countdown nobody can see is
/// not a limit, it is a surprise.
const left = ref(0);

/// Long enough to look at something, short enough that a window left open is
/// not a camera left on.
const SESSION = 120;

let stream: MediaStream | null = null;
let ticking = 0;

async function start() {
  if (!capturesHere) {
    // The app's lens belongs to the signed host, which hands over a frame and
    // never a preview. Saying so beats an empty rectangle.
    trouble.value =
      "The lens belongs to the signed host here, so there is no preview — " +
      "ask E.V. to look and it will take one frame.";
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
    if (feed.value) {
      feed.value.srcObject = stream;
      await feed.value.play();
    }
    emit("live", true);
    left.value = SESSION;
    ticking = window.setInterval(() => {
      left.value -= 1;
      if (left.value <= 0) emit("close");
    }, 1000);
  } catch (error) {
    // A refusal is an answer, and it is the user's. It is reported, not
    // retried.
    trouble.value = String(error instanceof Error ? error.message : error);
  }
}

function stop() {
  window.clearInterval(ticking);
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  emit("live", false);
}

/// One frame, down the path that already exists. The still is made here,
/// submitted, and dropped -- it is never held, and never written anywhere.
async function take() {
  const video = feed.value;
  if (!video || asking.value) return;
  asking.value = true;

  try {
    const still = document.createElement("canvas");
    still.width = video.videoWidth;
    still.height = video.videoHeight;
    still.getContext("2d")?.drawImage(video, 0, 0);
    const answer = await look(still.toDataURL("image/jpeg", 0.82), null, props.locale);
    emit("said", answer.spoken?.join(" ") || answer.speech || answer.outcome);
  } catch (error) {
    trouble.value = String(error instanceof Error ? error.message : error);
  } finally {
    asking.value = false;
  }
}

onMounted(start);
onBeforeUnmount(stop);
</script>

<template>
  <section class="surface">
    <div class="frame">
      <!-- Desaturated and cooled, like everything else that is an image on a
           display made of one hue. -->
      <video ref="feed" class="feed" playsinline muted />

      <p v-if="trouble" class="trouble">{{ trouble }}</p>

      <!-- The reticle: a thin cross and four framing brackets. It is also the
           active-state indicator, and it is on screen for exactly as long as
           the lens is. -->
      <span class="reticle" />
      <span class="bracket tl" />
      <span class="bracket tr" />
      <span class="bracket bl" />
      <span class="bracket br" />

      <span class="label">cam_01 // {{ trouble ? "no feed" : "live" }}</span>
      <span v-if="left > 0" class="left">{{ left }}s</span>
    </div>

    <div class="acts">
      <button v-if="capturesHere" type="button" :disabled="asking" @click="take">
        {{ asking ? "[ looking... ]" : "[ look ↵ ]" }}
      </button>
      <button type="button" @click="emit('close')">[ close ]</button>
    </div>
  </section>
</template>

<style scoped>
.surface {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  z-index: 6;
}

.frame {
  position: relative;
  width: min(62vw, 74vh);
  aspect-ratio: 4 / 3;
  border: 1px solid var(--panel-border);
  background: rgba(6, 10, 18, 0.6);
  overflow: hidden;
}

.feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  /* Cooled and dimmed: a camera feed at full colour is the brightest thing
     that has ever been on this display, and it would own it. */
  filter: saturate(0.5) contrast(1.05) brightness(0.85);
}

.trouble {
  position: absolute;
  inset: auto 16px;
  top: 50%;
  margin: 0;
  transform: translateY(-50%);
  text-align: center;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
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
  opacity: 0.25;
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

.acts {
  display: flex;
  gap: 18px;
}

.acts button {
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: 0.12em;
  color: var(--muted);
  cursor: pointer;
}

.acts button:hover:not(:disabled) {
  color: var(--neon-soft);
}

.acts button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
