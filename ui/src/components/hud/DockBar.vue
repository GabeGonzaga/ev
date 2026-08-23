<script setup lang="ts">
// The dock: six thin outlined icons and a home indicator, bottom centre.
//
// Quiet by default. Every icon sits at `--muted` and takes the neon only
// while the thing it stands for is actually live -- the camera while the lens
// is on, the microphone while it is open, a widget while it is up. An
// interface where everything glows says nothing by glowing, and this row is
// the one place where "lit" has to mean something.
//
// Inline SVG rather than an icon set: six paths at one stroke weight is less
// code than a dependency, and the weight has to match the linework around it.

export type DockAction =
  | "camera"
  | "microphone"
  | "music"
  | "shortcuts"
  | "add"
  | "chat"
  | "map";

import { t } from "../../i18n";

defineProps<{
  /// Which of them are live right now.
  lit?: Partial<Record<DockAction, boolean>>;
}>();

const emit = defineEmits<{ pick: [action: DockAction] }>();

// The titles live in the locale file under the action's own name, so the
// list here is only the order of the row.
const ICONS: { action: DockAction }[] = [
  { action: "camera" },
  { action: "microphone" },
  { action: "music" },
  { action: "shortcuts" },
  { action: "add" },
  { action: "chat" },
  { action: "map" },
];
</script>

<template>
  <nav class="dock">
    <button
      v-for="icon in ICONS"
      :key="icon.action"
      class="key"
      :class="{ on: lit?.[icon.action] }"
      type="button"
      :title="t(`dock.${icon.action}`)"
      @click="emit('pick', icon.action)"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <template v-if="icon.action === 'camera'">
          <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.2-2h8.2l1.2 2h2.2A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z" />
          <circle cx="12" cy="13" r="3.6" />
        </template>
        <template v-else-if="icon.action === 'microphone'">
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5.5 12a6.5 6.5 0 0 0 13 0M12 18.5V21" />
        </template>
        <template v-else-if="icon.action === 'map'">
          <path d="M9 4.5 3.5 6.8v12.7L9 17.2l6 2.3 5.5-2.3V4.5L15 6.8z" />
          <path d="M9 4.5v12.7M15 6.8v12.7" />
        </template>
        <template v-else-if="icon.action === 'music'">
          <path d="M9 18V6l10-2v12" />
          <circle cx="6.5" cy="18" r="2.5" />
          <circle cx="16.5" cy="16" r="2.5" />
        </template>
        <template v-else-if="icon.action === 'shortcuts'">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M3.5 12h17M12 3.5c4 4.5 4 12.5 0 17M12 3.5c-4 4.5-4 12.5 0 17" />
        </template>
        <template v-else-if="icon.action === 'add'">
          <path d="M12 5.5v13M5.5 12h13" />
        </template>
        <template v-else>
          <path d="M4 6.5h16v10H9.5L5.5 20v-3.5H4z" />
        </template>
      </svg>
    </button>
  </nav>
  <!-- The short rounded bar beneath: it says the row above is the edge of the
       interface and there is nothing under it. -->
  <span class="indicator" />
</template>

<style scoped>
.dock {
  position: absolute;
  left: 50%;
  bottom: 34px;
  transform: translateX(-50%);
  display: flex;
  gap: 24px;
  z-index: 5;
}

.key {
  width: 16px;
  height: 16px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.18s, filter 0.18s;
}

.key svg {
  width: 100%;
  height: 100%;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.key:hover {
  color: #fff;
}

.key.on {
  color: var(--neon);
  filter: drop-shadow(0 0 5px rgba(63, 165, 246, 0.75));
}

.indicator {
  position: absolute;
  left: 50%;
  bottom: 18px;
  width: 96px;
  height: 3px;
  margin-left: -48px;
  border-radius: 2px;
  background: rgba(200, 224, 245, 0.28);
  z-index: 5;
}
</style>
