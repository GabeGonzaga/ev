<script setup lang="ts">
// The box every panel is drawn in, and the three things every panel has to
// be able to say.
//
// Waiting, failed, and here-it-is. A panel that only renders the third one
// hides the first failure it ever has, and this display is meant to be an
// instrument: an instrument that goes blank when its sensor breaks is worse
// than one that says the sensor broke. So the failure is printed, in the
// panel, as terminal output -- not swallowed, not a toast somewhere else, not
// an empty box that looks like a quiet afternoon.
//
// It knows nothing about where anything came from. Everything arrives as a
// prop so any panel can be mounted on its own with values typed in by hand.

import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /// The three parts of the header, in `NAME // SUBTITLE // SOURCE` order.
    /// Missing parts are left out rather than printed as gaps.
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
  }>(),
  { waiting: "awaiting stream" },
);

const label = computed(() =>
  [props.name, props.subtitle, props.source].filter(Boolean).join(" // "),
);
</script>

<template>
  <section class="pane" :class="{ live }">
    <header>
      <span class="label">{{ label }}</span>
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
  /* Two, and never more. A HUD with rounded panels is a settings screen. */
  border-radius: 2px;
  backdrop-filter: blur(8px);
}

.pane.live {
  border-color: rgba(61, 155, 255, 0.5);
  box-shadow: var(--neon-glow);
}

header {
  padding: 7px 10px 6px;
  border-bottom: 1px solid var(--panel-border);
}

.label {
  font-family: var(--mono);
  font-size: var(--label);
  letter-spacing: var(--label-track);
  text-transform: uppercase;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
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
</style>
