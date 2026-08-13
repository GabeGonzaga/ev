<script setup lang="ts">
import { ref } from "vue";
import { canBindKeys } from "../api";
import { useSession } from "../stores/session";

const session = useSession();
const open = ref(false);

// Recorded as it is typed, so "⌘⇧Space" is one gesture rather than something
// to spell. The app answers whether it could take the key.
function record(event: KeyboardEvent) {
  event.preventDefault();
  if (["Meta", "Shift", "Alt", "Control"].includes(event.key)) return;

  const parts = [];
  if (event.metaKey) parts.push("CmdOrCtrl");
  if (event.ctrlKey && !event.metaKey) parts.push("Ctrl");
  if (event.altKey) parts.push("Alt");
  if (event.shiftKey) parts.push("Shift");
  parts.push(event.code.replace(/^Key|^Digit/, ""));

  if (parts.length < 2) return;
  void session.bind(parts.join("+"));
}

/// ⌘⇧Space rather than CmdOrCtrl+Shift+Space: the keys as they are printed on
/// them. What is stored is the other spelling, which is the plugin's.
function pretty(binding: string): string {
  return binding
    .split("+")
    .map(
      (part) =>
        ({
          CmdOrCtrl: "⌘",
          Cmd: "⌘",
          Ctrl: "⌃",
          Alt: "⌥",
          Shift: "⇧",
          Space: "Space",
        })[part] ?? part,
    )
    .join("");
}
</script>

<template>
  <section class="settings">
    <button type="button" class="toggle" @click="open = !open">
      <span class="chevron" :class="{ open }">›</span>
      settings
    </button>

    <div v-if="open" class="rows">
      <label>
        <span>Language</span>
        <select
          :value="session.locale"
          @change="session.choose(($event.target as HTMLSelectElement).value)"
        >
          <option value="pt-PT">Português (PT)</option>
          <option value="en">English</option>
        </select>
      </label>

      <label v-if="canBindKeys">
        <span>Hold to talk</span>
        <input
          readonly
          class="key"
          :value="pretty(session.shortcut)"
          placeholder="click, then press a combination"
          @keydown="record"
        />
      </label>

      <p v-if="session.shortcutTrouble" class="trouble">
        {{ session.shortcutTrouble }}
      </p>
      <p v-else-if="canBindKeys" class="note">
        Hold it anywhere to talk. Let go and E.V. answers.
      </p>
    </div>
  </section>
</template>

<style scoped>
.toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--muted);
  padding: 2px 0;
}

.chevron {
  display: inline-block;
  transition: transform 0.15s;
}

.chevron.open {
  transform: rotate(90deg);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

select,
.key {
  padding: 3px 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--field);
  font-size: 12px;
  min-width: 160px;
  text-align: center;
}

.key {
  font-family: var(--mono);
  cursor: pointer;
}

.note {
  margin: 0;
  font-size: 11px;
  color: var(--faint);
}

.trouble {
  margin: 0;
  font-size: 11px;
  color: var(--bad);
}
</style>
