<script setup lang="ts">
import { useWorkspace } from "../stores/workspace";
import { useSession } from "../stores/session";

const workspace = useWorkspace();
const session = useSession();

/// Four glyphs, one per widget or surface. Drawn rather than fetched: an
/// icon font is one more thing that can fail to load under a policy that
/// allows nothing off this machine.
const ICONS = {
  system: "M12 2 L14.5 9.5 L22 12 L14.5 14.5 L12 22 L9.5 14.5 L2 12 L9.5 9.5 Z",
  chat: "M3 5h18v12H8l-5 4z",
  camera: "M4 7h4l2-2h4l2 2h4v12H4z M12 12.5m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0",
  music: "M9 18V6l10-2v12 M9 18a3 3 0 1 1-6 0a3 3 0 0 1 6 0 M19 16a3 3 0 1 1-6 0a3 3 0 0 1 6 0",
} as const;

const items = [
  { id: "console", label: "system", path: ICONS.system },
  { id: "chat", label: "chat", path: ICONS.chat },
  { id: "camera", label: "camera", path: ICONS.camera },
  { id: "music", label: "music", path: ICONS.music },
] as const;
</script>

<template>
  <div class="dock-cluster">
    <nav class="dock">
      <template v-for="(item, index) in items" :key="item.id">
        <span v-if="index" class="divider" />
        <button
          type="button"
          :class="{ open: workspace.isOpen(item.id) }"
          :title="item.label"
          @click="workspace.toggle(item.id)"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path :d="item.path" />
          </svg>
        </button>
      </template>
    </nav>

    <!-- Beneath it, the session: the pill fills toward the accent while the
         microphone is open. -->
    <div class="pulse">
      <span class="dot" />
      <span class="pill" :class="{ live: session.state === 'listening' }" />
      <span class="dot" />
    </div>
  </div>
</template>

<style scoped>
.dock-cluster {
  position: fixed;
  bottom: 22px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 6;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
}

.dock {
  display: flex;
  align-items: center;
  gap: 6px;
}

button {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  color: rgba(var(--tick), 0.45);
  transition: color 0.15s, background 0.15s;
}

button:hover {
  color: rgba(242, 245, 248, 0.9);
}

/* Open is the one state with a background: a lit box, quietly. */
button.open {
  color: var(--text);
  background: rgba(var(--accent), 0.2);
}

svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.divider {
  width: 1px;
  height: 14px;
  background: rgba(var(--tick), 0.25);
}

.pulse {
  display: flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: rgba(var(--tick), 0.35);
}

.pill {
  width: 34px;
  height: 4px;
  border-radius: 2px;
  background: rgba(var(--tick), 0.18);
  overflow: hidden;
  position: relative;
}

.pill.live::after {
  content: "";
  position: absolute;
  inset: 0;
  background: rgb(var(--accent));
  animation: fill 1.4s ease-in-out infinite;
  transform-origin: left;
}

@keyframes fill {
  0%, 100% { transform: scaleX(0.15); }
  50% { transform: scaleX(1); }
}
</style>
