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

/// Which edges a handle pulls. A corner pulls two.
interface Pull {
  at: string;
  left?: boolean;
  right?: boolean;
  top?: boolean;
  bottom?: boolean;
  cursor: string;
}

/// Every edge and every corner, not one 16px square in the corner. A window
/// that can only be resized from a single hidden target is a window most
/// people conclude cannot be resized -- which is exactly what happened.
const HANDLES: Pull[] = [
  { at: "n", top: true, cursor: "ns-resize" },
  { at: "s", bottom: true, cursor: "ns-resize" },
  { at: "w", left: true, cursor: "ew-resize" },
  { at: "e", right: true, cursor: "ew-resize" },
  { at: "nw", top: true, left: true, cursor: "nwse-resize" },
  { at: "ne", top: true, right: true, cursor: "nesw-resize" },
  { at: "sw", bottom: true, left: true, cursor: "nesw-resize" },
  { at: "se", bottom: true, right: true, cursor: "nwse-resize" },
];

/// Both gestures are the same shape: remember where the pointer started and
/// what the window was, then write the difference on every move. Pointer
/// capture, because at any real drag speed the pointer outruns the window.
function grab(event: PointerEvent, what: "move" | Pull) {
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

    if (what === "move") {
      workspace.move(props.name, { ...was, x: was.x + dx, y: was.y + dy });
      return;
    }

    // Pulling the top or the left moves the window as well as sizing it:
    // the opposite edge is what has to stay still.
    const next = { ...was };
    if (what.right) next.width = was.width + dx;
    if (what.bottom) next.height = was.height + dy;
    if (what.left) {
      next.x = was.x + dx;
      next.width = was.width - dx;
    }
    if (what.top) {
      next.y = was.y + dy;
      next.height = was.height - dy;
    }
    workspace.move(props.name, next);
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

    <template v-if="movable">
      <span
        v-for="pull in HANDLES"
        :key="pull.at"
        class="pull"
        :class="pull.at"
        :style="{ cursor: pull.cursor }"
        @pointerdown="grab($event, pull)"
      />
    </template>
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

/* Every edge and every corner. Six pixels of reach, which is invisible and
   findable -- the corners overlap the edges and win by coming later. */
.pull {
  position: absolute;
  touch-action: none;
}

.pull.n,
.pull.s {
  left: 6px;
  right: 6px;
  height: 6px;
}

.pull.n {
  top: -3px;
}

.pull.s {
  bottom: -3px;
}

.pull.w,
.pull.e {
  top: 6px;
  bottom: 6px;
  width: 6px;
}

.pull.w {
  left: -3px;
}

.pull.e {
  right: -3px;
}

.pull.nw,
.pull.ne,
.pull.sw,
.pull.se {
  width: 14px;
  height: 14px;
}

.pull.nw {
  top: -3px;
  left: -3px;
}

.pull.ne {
  top: -3px;
  right: -3px;
}

.pull.sw {
  bottom: -3px;
  left: -3px;
}

.pull.se {
  bottom: -3px;
  right: -3px;
}
</style>
