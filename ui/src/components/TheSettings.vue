<script setup lang="ts">
import { ref, watch } from "vue";
import { canBindKeys } from "../api";
import { useSession } from "../stores/session";

const session = useSession();

// Typed here, saved on Enter or on leaving the field -- not on every
// keystroke, which would have E.V. answering to `e`, then `ev`, then `evi`
// on the way to `evie`.
const name = ref(session.wake?.word ?? "");
watch(
  () => session.wake?.word,
  (word) => (name.value = word ?? ""),
);

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
        ({ CmdOrCtrl: "⌘", Cmd: "⌘", Ctrl: "⌃", Alt: "⌥", Shift: "⇧" })[part] ??
        part,
    )
    .join("");
}
</script>

<template>
  <div class="rows">
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
        placeholder="click, then press"
        @keydown="record"
      />
    </label>

    <template v-if="session.wake">
      <label>
        <span>Answers to</span>
        <input
          v-model="name"
          class="key"
          spellcheck="false"
          placeholder="ev"
          @keydown.enter="session.name(name, session.wake.enabled)"
          @blur="session.name(name, session.wake.enabled)"
        />
      </label>

      <label>
        <span>Listen for it</span>
        <button
          class="toggle"
          type="button"
          :class="{ on: session.wake.enabled }"
          @click="session.name(name, !session.wake.enabled)"
        >
          {{ session.wake.enabled ? "on" : "off" }}
        </button>
      </label>

      <!-- Said plainly, where it is switched on. While this runs, everything
           spoken near the machine is transcribed on it. Nothing leaves and
           nothing is kept, and that is still worth reading before agreeing
           to it. -->
      <p class="aside">
        While this is on, E.V. transcribes what it hears on this machine to
        find its name. Nothing leaves it, and only what began with the name is
        recorded.
      </p>
    </template>

    <p v-if="session.wakeTrouble" class="trouble">{{ session.wakeTrouble }}</p>

    <p v-if="session.shortcutTrouble" class="trouble">
      {{ session.shortcutTrouble }}
    </p>
  </div>
</template>

<style scoped>
.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: var(--muted);
}

select {
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%),
    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: right 10px center, right 6px center;
  background-size: 4px 4px, 4px 4px;
  background-repeat: no-repeat;
}

select,
.key {
  padding: 3px 8px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--field);
  color: var(--text);
  font-size: 11px;
  min-width: 150px;
  text-align: center;
}

.key {
  font-family: var(--mono);
  cursor: pointer;
}

select:focus,
.key:focus {
  outline: none;
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.toggle {
  padding: 3px 8px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--field);
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11px;
  min-width: 150px;
  letter-spacing: 0.1em;
}

.toggle.on {
  color: var(--live);
  border-color: var(--live);
}

.aside {
  margin: 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--faint);
}

.trouble {
  margin: 0;
  font-size: 11px;
  color: var(--bad);
}
</style>
