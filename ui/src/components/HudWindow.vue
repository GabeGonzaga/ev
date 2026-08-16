<script setup lang="ts">
import { computed } from "vue";
import { useWindows, type Spawn } from "../stores/windows";

/// A floating widget: the same squared, bracketed panel as the docked ones,
/// but one you drag by its bar, size by its corner, and close when you are
/// done. The chrome is the only thing added here; what goes inside is a slot,
/// so a window is a frame and nothing more.
const props = defineProps<{
  id: string;
  label: string;
  spawn: Spawn;
  live?: boolean;
}>();

const windows = useWindows();
// Defined in setup, not on mount, so the frame exists before the first render
// reads its geometry. Returns the reactive frame, so the template follows it.
const frame = windows.define(props.id, props.spawn);
const open = computed(() => frame.open);

/// Drag by the bar. The pointer is tracked on the window, not the header, so a
/// fast drag that outruns the cursor does not drop the window behind.
function startMove(event: PointerEvent) {
  windows.raise(props.id);
  const sx = event.clientX;
  const sy = event.clientY;
  const ox = frame.x;
  const oy = frame.y;
  const move = (e: PointerEvent) =>
    windows.moveTo(props.id, ox + e.clientX - sx, oy + e.clientY - sy);
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

/// Size from the corner grip. The window's minimum is the store's, so a
/// widget can never be dragged smaller than the thing inside it needs.
function startResize(event: PointerEvent) {
  windows.raise(props.id);
  const sx = event.clientX;
  const sy = event.clientY;
  const ow = frame.w;
  const oh = frame.h;
  const move = (e: PointerEvent) =>
    windows.sizeTo(props.id, ow + e.clientX - sx, oh + e.clientY - sy);
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}
</script>

<template>
  <section
    v-if="open"
    class="hud window"
    :class="{ live }"
    :style="{
      position: 'absolute',
      left: frame.x + 'px',
      top: frame.y + 'px',
      width: frame.w + 'px',
      height: frame.h + 'px',
      zIndex: frame.z,
    }"
    @pointerdown="windows.raise(id)"
  >
    <!-- The bar is the handle: grab it to move the window. The label reads as
         a lit tab, the way the design names each panel. -->
    <header class="bar" @pointerdown.stop="startMove">
      <span class="tab">{{ label }}</span>
      <span class="grip" aria-hidden="true"><i /><i /><i /></span>
      <span class="spacer" />
      <button
        class="x"
        type="button"
        title="close"
        aria-label="close"
        @pointerdown.stop
        @click="windows.close(id)"
      >
        ✕
      </button>
    </header>

    <div class="body">
      <slot />
    </div>

    <!-- The corner grip: drag it to resize. Two short strokes, the HUD's own
         way of saying "pull here". -->
    <button
      class="resize"
      type="button"
      title="resize"
      aria-label="resize"
      @pointerdown.stop.prevent="startResize"
    />
  </section>
</template>

<style scoped>
.window {
  /* Sits over the grid and the orb; the store's z-order decides which window
     wins when two overlap. Geometry is inline, so it beats .hud's relative. */
  overflow: hidden;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  padding: 0;
}

.window.live {
  border-color: var(--panel-lit);
  box-shadow: var(--glow), 0 18px 50px rgba(0, 0, 0, 0.5);
}

.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  /* The global `.hud > header` gives every panel header a bottom margin; a
     title bar that is also the drag handle wants its border flush instead. */
  margin: 0;
  padding: 7px 8px 7px 10px;
  cursor: grab;
  user-select: none;
  border-bottom: 1px solid var(--line);
  /* A faint lit strip along the top, so the bar reads as the live edge the
     way the design's headers do. */
  background: linear-gradient(180deg, rgba(var(--accent), 0.12), transparent);
}

.bar:active {
  cursor: grabbing;
}

/* The lit name tab: bracketed, uppercase mono, the accent -- the same mark
   the docked panels wear, here doubling as what you grab. */
.tab {
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink);
  padding: 2px 8px;
  border: 1px solid var(--panel-lit);
  border-radius: 2px;
  background: rgba(var(--accent), 0.14);
  box-shadow: var(--glow);
}

/* Three short bars: the universal "drag me", quiet next to the tab. */
.grip {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0.4;
}

.grip i {
  width: 12px;
  height: 1px;
  background: var(--faint);
}

.spacer {
  flex: 1;
}

.x {
  font-size: 10px;
  line-height: 1;
  color: var(--faint);
  padding: 3px 5px;
  border: 1px solid transparent;
  border-radius: 2px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.x:hover {
  color: var(--text);
  border-color: var(--bad);
  background: rgba(255, 77, 77, 0.12);
}

.body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px 12px 12px;
}

/* The resize grip, bottom-right, over the panel's own corner bracket. Drawn
   as two nested strokes with a border gradient. */
.resize {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  padding: 0;
  cursor: nwse-resize;
  background: linear-gradient(
    135deg,
    transparent 0 45%,
    var(--panel-lit) 45% 55%,
    transparent 55% 70%,
    var(--panel-lit) 70% 80%,
    transparent 80%
  );
  opacity: 0.7;
}

.resize:hover {
  opacity: 1;
}
</style>
