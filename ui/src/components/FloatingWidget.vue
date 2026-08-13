<script setup lang="ts">
import { computed, ref } from "vue";
import { useWorkspace, type Thing } from "../stores/workspace";

const props = defineProps<{ id: Thing; tag: string; at: { x: number; y: number } }>();

const workspace = useWorkspace();

/// A stable pseudo-identifier per widget. Decorative, and deliberately so:
/// it is the strongest identity cue the widget system has, and a code that
/// changed on every render would read as noise instead of as a serial number.
const code = computed(() => {
  let hash = 0;
  for (const character of props.id) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return `${props.tag}_${hash.toString(16).toUpperCase().padStart(6, "0")}I`;
});

const place = computed(() => workspace.places[props.id] ?? props.at);

/// Dragged by the tab or by any part of the chrome. No snapping, no tiling,
/// no auto-arrangement: this is a workspace, and things are placed rather
/// than laid out.
const dragging = ref<{ x: number; y: number } | null>(null);

function grab(event: PointerEvent) {
  if ((event.target as HTMLElement).closest("input, textarea, button.control")) return;
  workspace.raise(props.id);
  dragging.value = { x: event.clientX - place.value.x, y: event.clientY - place.value.y };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function move(event: PointerEvent) {
  if (!dragging.value) return;
  workspace.place(props.id, {
    x: event.clientX - dragging.value.x,
    y: event.clientY - dragging.value.y,
  });
}

function drop() {
  dragging.value = null;
}
</script>

<template>
  <section
    class="widget"
    :style="{ left: `${place.x}px`, top: `${place.y}px`, zIndex: workspace.depth(id) }"
    @pointerdown="grab"
    @pointermove="move"
    @pointerup="drop"
    @pointercancel="drop"
  >
    <!-- The tab: chamfered, never rounded, filled with the accent, carrying
         an identifier nobody needs to read. -->
    <span class="tab">{{ code }}</span>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.widget {
  position: fixed;
  width: 340px;
  max-height: 62vh;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  border: 1px solid rgba(var(--tick), 0.25);
  background: rgba(20, 23, 28, 0.85);
  backdrop-filter: blur(14px);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.55);
  cursor: grab;
  touch-action: none;
}

.widget:active {
  cursor: grabbing;
}

.tab {
  position: absolute;
  top: -15px;
  left: 10px;
  padding: 2px 8px 1px;
  font-family: var(--terminal);
  font-size: 9px;
  line-height: 1.4;
  letter-spacing: 0.06em;
  color: #06121e;
  background: rgb(var(--accent));
  /* Clipped corners, not rounded: the one shape in the interface that is. */
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);
}

.body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 14px 14px 12px;
  gap: 8px;
  overflow: hidden;
}
</style>
