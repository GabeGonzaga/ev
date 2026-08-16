<script setup lang="ts">
// The box every panel is drawn in, wherever it is drawn.
//
// One frame. Docked in a grid slot or floating over the display, a panel is
// the same component with the same border, the same header and the same
// corner ticks -- only the geometry changes hands, from the grid to the
// person. An interface where a floating window looks different from a docked
// one is two interfaces, and the difference accumulates quietly: each new
// panel looks reasonable on its own.
//
// It also owns the three things every panel has to be able to say: waiting,
// failed, and here-it-is. A panel that renders only the third one hides the
// first failure it ever has, and an instrument that goes blank when its
// sensor breaks is worse than one that says the sensor broke. So the failure
// is printed, in the panel, as terminal output.
//
// Everything about the data arrives as a prop, so any panel can be mounted on
// its own with values typed in by hand.

import { computed, ref } from "vue";
import { LEAST_TALL, LEAST_WIDE, useWorkspace } from "../../stores/workspace";

const props = withDefaults(
  defineProps<{
    /// The three parts of the header, in `NAME // SUBTITLE // SOURCE` order.
    /// Missing parts are left out rather than printed as gaps. The name is
    /// also the panel's identity in the workspace.
    name: string;
    subtitle?: string;
    source?: string;
    pending?: boolean;
    error?: string | null;
    /// Nothing wrong, nothing to show yet. Says so in the same voice as the
    /// loading line, because to a reader they are the same situation.
    empty?: boolean;
    waiting?: string;
    /// Something in it is live -- a stream arriving, a camera on. Lights the
    /// border, which is the only thing on this display that means "now".
    live?: boolean;
    /// Off for a popover, which is a frame but not a panel: it has nowhere to
    /// dock back to.
    movable?: boolean;
  }>(),
  { waiting: "awaiting stream", movable: true },
);

const workspace = useWorkspace();
const shell = ref<HTMLElement | null>(null);

const label = computed(() =>
  [props.name, props.subtitle, props.source].filter(Boolean).join(" // "),
);

const floating = computed(() => props.movable && workspace.isFloating(props.name));

/// Where this panel is on screen right now, whichever way it is placed. Used
/// to open it exactly where it already is, so picking a panel up does not
/// teleport it.
function here() {
  const box = shell.value?.getBoundingClientRect();
  if (!box) return { x: 120, y: 120, width: LEAST_WIDE, height: LEAST_TALL };
  return { x: box.left, y: box.top, width: box.width, height: box.height };
}

function toggle() {
  workspace.toggle(props.name, here());
}

// --- moving and sizing ---------------------------------------------------

/// Both gestures are the same shape: remember where the pointer started and
/// what the panel was, then write the difference on every move. Pointer
/// capture means the panel keeps receiving moves even when the pointer
/// outruns it, which at any real drag speed it does.
function grab(event: PointerEvent, what: "move" | "size") {
  if (!floating.value && what === "size") return;
  if (event.button !== 0) return;

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
  if (!floating.value || at === "docked") return undefined;
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
  <!-- Floating panes leave the grid for the body. A grid cell carries a
       transform while it arrives, and a transformed ancestor is the
       containing block for `position: fixed` -- so a window left inside one
       would be positioned against its old slot instead of the display. -->
  <Teleport to="body" :disabled="!floating">
  <section
    ref="shell"
    class="pane"
    :class="{ live, floating }"
    :style="geometry"
    @pointerdown="floating && workspace.raise(name)"
  >
    <header :class="{ handle: floating }" @pointerdown="grab($event, 'move')">
      <span class="label">{{ label }}</span>

      <!-- The way out, and the way back, in one control. There is never a
           placement with no way to leave it: that is how the old view trapped
           a widget on the floor with the button to undo it hidden. -->
      <button
        v-if="movable"
        class="control"
        type="button"
        :title="floating ? 'back to its slot' : 'open as a window'"
        @pointerdown.stop
        @click="toggle"
      >
        {{ floating ? "▣" : "◱" }}
      </button>
    </header>

    <!-- Corner ticks, one per corner. Brackets rather than a heavier border:
         the eye reads a corner as a frame and stops looking at it. -->
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

    <!-- Floating only: docked, the grid owns the size. -->
    <span v-if="floating" class="grip" @pointerdown="grab($event, 'size')" />
  </section>
  </Teleport>
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
  /* Two, and never more. A HUD with rounded panels is a settings screen. */
  border-radius: 2px;
  backdrop-filter: blur(8px);
}

/* Out of the grid. Same frame, same everything -- it is simply the person
   holding the geometry now instead of the layout. */
.pane.floating {
  position: fixed;
  /* Opaque enough to read over whatever it is covering; the docked ones sit
     on the background and can afford to be thinner. */
  background: color-mix(in srgb, var(--panel-fill) 88%, #04070e);
  border-color: rgba(90, 160, 255, 0.4);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.5);
}

.pane.live {
  border-color: rgba(61, 155, 255, 0.5);
  box-shadow: var(--neon-glow);
}

header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px 6px 10px;
  border-bottom: 1px solid var(--panel-border);
}

/* The whole header, not a dedicated grab bar: the bar would be one more thing
   on screen that does nothing else. */
header.handle {
  cursor: grab;
  touch-action: none;
}

header.handle:active {
  cursor: grabbing;
}

.label {
  flex: 1;
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: var(--label-track);
  text-transform: uppercase;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.control {
  flex: 0 0 auto;
  padding: 0 3px;
  border: 0;
  background: none;
  font-size: 10px;
  line-height: 1;
  color: var(--text-dim);
  cursor: pointer;
}

.control:hover {
  color: var(--neon-bright);
  text-shadow: var(--neon-glow-text);
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
  /* Nothing leaves the frame. A pane given one grid row is shorter than its
     own first line, and the line was hanging out below the border. */
  overflow: hidden;
  padding: 10px;
  font-family: var(--mono);
  font-size: var(--body);
}

.waiting {
  margin: 0;
  color: var(--text-dim);
}

/* Printed, not hidden. Red-tinted terminal output, wrapping rather than
   truncating: the end of an error message is usually the useful half. */
.failed {
  margin: 0;
  color: var(--error);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.55;
}

/* Sized from the corner the eye already reads as the corner -- the bottom
   bracket doubles as the grip rather than adding a second mark beside it. */
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
