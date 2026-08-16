<script setup lang="ts">
// The frame everything is drawn in.
//
// One frame: every widget, every popover, every window. Nothing draws its own
// border, its own header or its own corners, because an interface where two
// panels differ in their chrome is two interfaces, and the difference
// accumulates quietly -- each new panel looks reasonable on its own.
//
// A squared body, a thin lit edge, corner brackets, and a small tab at the
// top carrying an uppercase mono label. The tab is also the handle: there is
// no separate title bar, because a bar would be one more thing on screen that
// does nothing else.
//
// It also owns the three things a panel has to be able to say -- waiting,
// failed, and here-it-is. A panel that renders only the third hides the first
// failure it ever has, and an instrument that goes blank when its sensor
// breaks is worse than one that says the sensor broke.

import { computed, onMounted } from "vue";
import { type Floating, useWorkspace } from "../../stores/workspace";

const props = withDefaults(
  defineProps<{
    /// The tab's label, and the window's identity in the workspace.
    name: string;
    pending?: boolean;
    error?: string | null;
    empty?: boolean;
    waiting?: string;
    /// Something in it is live. Lights the edge, which is the only thing on
    /// this display that means "now".
    live?: boolean;
    /// Where it opens, the first time. Afterwards it is wherever it was left.
    at?: Floating;
    /// Off for a popover: a frame, but not a window -- nothing to move, and
    /// nothing to remember about it.
    movable?: boolean;
    closable?: boolean;
  }>(),
  { waiting: "awaiting stream", movable: true, closable: true },
);

const emit = defineEmits<{ close: [] }>();

const workspace = useWorkspace();

onMounted(() => {
  // First time open: put it where it was told to. After that the workspace
  // knows, and a window opens where it was left.
  if (props.movable && props.at && !workspace.isFloating(props.name)) {
    workspace.open(props.name, props.at);
  }
});

// --- moving and sizing ---------------------------------------------------

/// Both gestures are the same shape: remember where the pointer started and
/// what the window was, then write the difference on every move. Pointer
/// capture, because at any real drag speed the pointer outruns the window.
function grab(event: PointerEvent, what: "move" | "size") {
  if (!props.movable || event.button !== 0) return;
  const from = workspace.placement(props.name);
  if (from === "docked") return;

  workspace.raise(props.name);
  const startX = event.clientX;
  const startY = event.clientY;
  const was = { ...from };
  const handle = event.currentTarget as HTMLElement;
  handle.setPointerCapture(event.pointerId);
  event.preventDefault();

  function onMove(moved: PointerEvent) {
    const dx = moved.clientX - startX;
    const dy = moved.clientY - startY;
    workspace.move(
      props.name,
      what === "move"
        ? { ...was, x: was.x + dx, y: was.y + dy }
        : { ...was, width: was.width + dx, height: was.height + dy },
    );
  }

  function done() {
    handle.releasePointerCapture(event.pointerId);
    handle.removeEventListener("pointermove", onMove);
    handle.removeEventListener("pointerup", done);
    handle.removeEventListener("pointercancel", done);
  }

  handle.addEventListener("pointermove", onMove);
  handle.addEventListener("pointerup", done);
  handle.addEventListener("pointercancel", done);
}

const geometry = computed(() => {
  const at = workspace.placement(props.name);
  if (!props.movable || at === "docked") return undefined;
  return {
    left: `${at.x}px`,
    top: `${at.y}px`,
    width: `${at.width}px`,
    height: `${at.height}px`,
    zIndex: String(20 + workspace.depth(props.name)),
  };
});
</script>

<template>
  <section
    class="pane"
    :class="{ live, movable }"
    :style="geometry"
    @pointerdown="movable && workspace.raise(name)"
  >
    <!-- The tab: small, lit, and the handle. -->
    <header>
      <span class="tab" @pointerdown="grab($event, 'move')">{{ name }}</span>
      <span class="rule" @pointerdown="grab($event, 'move')" />
      <button
        v-if="closable"
        class="shut"
        type="button"
        title="close"
        @pointerdown.stop
        @click="emit('close')"
      >
        ×
      </button>
    </header>

    <!-- Corner brackets rather than a heavier border: the eye reads a corner
         as a frame and stops looking at it. -->
    <span class="tick tl" />
    <span class="tick tr" />
    <span class="tick bl" />
    <span class="tick br" />

    <div class="body">
      <p v-if="error" class="failed">{{ error }}</p>
      <p v-else-if="pending || empty" class="waiting">
        &gt; {{ waiting }}<span class="caret" />
      </p>
      <slot v-else />
    </div>

    <span v-if="movable" class="grip" @pointerdown="grab($event, 'size')" />
  </section>
</template>

<style scoped>
.pane {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: var(--panel-fill);
  border: 1px solid var(--panel-border);
  /* Squared. A HUD with rounded panels is a settings screen. */
  border-radius: 0;
  backdrop-filter: blur(9px);
}

.pane.movable {
  position: fixed;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.55);
}

.pane.live {
  border-color: rgba(63, 165, 246, 0.7);
  box-shadow: var(--neon-glow), 0 20px 60px rgba(0, 0, 0, 0.55);
}

header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 6px 0 8px;
  touch-action: none;
}

/* Lit, and the only lit thing on a panel that is not doing anything. */
.tab {
  padding: 3px 9px;
  border: 1px solid var(--panel-border);
  background: rgba(63, 165, 246, 0.12);
  font-family: var(--mono);
  font-size: var(--label);
  font-weight: 500;
  letter-spacing: var(--label-track);
  text-transform: uppercase;
  color: var(--neon-soft);
  white-space: nowrap;
  cursor: grab;
}

.tab:active {
  cursor: grabbing;
}

.rule {
  flex: 1;
  height: 1px;
  background: var(--panel-border);
  cursor: grab;
}

.shut {
  padding: 0 4px;
  border: 0;
  background: none;
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
}

.shut:hover {
  color: #fff;
}

.tick {
  position: absolute;
  width: 6px;
  height: 6px;
  border: 0 solid var(--neon-dim);
  pointer-events: none;
}

.tick.tl {
  top: 3px;
  left: 3px;
  border-top-width: 1px;
  border-left-width: 1px;
}

.tick.tr {
  top: 3px;
  right: 3px;
  border-top-width: 1px;
  border-right-width: 1px;
}

.tick.bl {
  bottom: 3px;
  left: 3px;
  border-bottom-width: 1px;
  border-left-width: 1px;
}

.tick.br {
  bottom: 3px;
  right: 3px;
  border-bottom-width: 1px;
  border-right-width: 1px;
}

.body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  /* Nothing leaves the frame. */
  overflow: hidden;
  padding: 10px;
  font-family: var(--mono);
  font-size: var(--body);
}

.waiting {
  margin: 0;
  color: var(--muted);
}

/* Printed, not hidden. Wrapping rather than truncating: the end of an error
   message is usually the useful half. */
.failed {
  margin: 0;
  color: var(--error);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.55;
}

/* The corner the eye already reads as a corner doubles as the grip. */
.grip {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  touch-action: none;
}
</style>
