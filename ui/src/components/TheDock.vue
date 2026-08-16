<script setup lang="ts">
import { computed } from "vue";
import { useSession } from "../stores/session";
import { useWindows } from "../stores/windows";

/// The row along the bottom: the widgets you open by hand, and the camera.
///
/// A window's icon lights while it is open, so the dock is also where the HUD
/// says what is on screen. The camera has no window -- it is the one-frame
/// look the rest of the app already uses -- so its icon lights only while the
/// lens is actually on (invariant 8: a visible active state, E.V.'s own).
const windows = useWindows();
const session = useSession();

const cameraBusy = computed(() => session.state !== "idle");
</script>

<template>
  <nav class="dock" aria-label="widgets">
    <button
      type="button"
      title="settings"
      :class="{ on: windows.isOpen('settings') }"
      @click="windows.toggle('settings')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="3.2" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
      </svg>
    </button>

    <button
      type="button"
      title="console"
      :class="{ on: windows.isOpen('console') }"
      @click="windows.toggle('console')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="1" />
        <path d="M7 9l3 3-3 3M13 15h4" />
      </svg>
    </button>

    <button
      type="button"
      title="camera"
      :class="{ on: session.camera }"
      :disabled="cameraBusy"
      @click="session.look()"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 8h4l2-3h6l2 3h4v11H3z" />
        <circle cx="12" cy="13" r="3.4" />
      </svg>
    </button>

    <button
      type="button"
      title="music"
      :class="{ on: windows.isOpen('music') }"
      @click="windows.toggle('music')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 18V5l10-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="16" cy="16" r="3" />
      </svg>
    </button>
  </nav>
</template>

<style scoped>
.dock {
  position: fixed;
  left: 50%;
  bottom: 14px;
  transform: translateX(-50%);
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 7px 14px;
  border-radius: 3px;
  border: 1px solid var(--line);
  background: rgba(4, 10, 18, 0.5);
  backdrop-filter: blur(8px);
}

button {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 24px;
  color: var(--faint);
  border-radius: 2px;
  border: 1px solid transparent;
  transition: color 0.15s, border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}

button:hover:not(:disabled) {
  color: var(--text);
}

button:disabled {
  opacity: 0.4;
}

/* Open, an icon lights the accent and wears the glow, the one lit thing in
   the row -- the same language the panels use for "live". */
button.on {
  color: var(--ink);
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
