<script setup lang="ts">
// The camera as a window: the same feed, small, movable, in the same frame as
// everything else.

import { ref } from "vue";
import { look } from "../../api";
import { still } from "../../composables/useCamera";
import CameraFeed from "./CameraFeed.vue";
import HudPane from "./HudPane.vue";

const props = withDefaults(
  defineProps<{
    stream: MediaStream | null;
    left: number;
    error?: string | null;
    locale?: string;
  }>(),
  { locale: "pt-PT", error: null },
);

const emit = defineEmits<{ close: []; expand: []; said: [text: string] }>();

const shown = ref<InstanceType<typeof CameraFeed> | null>(null);
const asking = ref(false);
const trouble = ref<string | null>(null);

/// One frame, down the path that already exists. The still is made here,
/// submitted, and dropped.
async function take() {
  const video = shown.value?.feed;
  if (!video || asking.value) return;
  const picture = still(video);
  if (!picture) return;

  asking.value = true;
  try {
    const answer = await look(picture, null, props.locale);
    emit("said", answer.spoken?.join(" ") || answer.speech || answer.outcome);
  } catch (failed) {
    trouble.value = String(failed instanceof Error ? failed.message : failed);
  } finally {
    asking.value = false;
  }
}
</script>

<template>
  <HudPane
    name="cam_01"
    :error="error ?? trouble"
    :live="!!stream"
    :at="{ x: 60, y: 420, width: 320, height: 260 }"
    @close="emit('close')"
  >
    <div class="body">
      <div class="picture">
        <CameraFeed ref="shown" :stream="stream" :left="left" />
      </div>
      <div class="acts">
        <button type="button" :disabled="asking" @click="take">
          {{ asking ? "[ looking... ]" : "[ look ↵ ]" }}
        </button>
        <button type="button" @click="emit('expand')">[ full screen ]</button>
      </div>
    </div>
  </HudPane>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
}

.picture {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--panel-border);
}

.acts {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

button {
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: 0.12em;
  color: var(--muted);
  cursor: pointer;
}

button:hover:not(:disabled) {
  color: var(--neon-soft);
}

button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
