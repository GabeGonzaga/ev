<script setup lang="ts">
import { ACCENTS, useAppearance } from "../stores/appearance";

const appearance = useAppearance();
const themes = ["system", "dark", "light"] as const;
</script>

<template>
  <div class="appearance">
    <div class="modes">
      <button
        v-for="mode in themes"
        :key="mode"
        type="button"
        :class="{ on: appearance.theme === mode }"
        @click="appearance.theme = mode"
      >
        {{ mode }}
      </button>
    </div>

    <!-- The evolutions. A hue each, and nothing else about the interface
         changes -- which is the whole appeal of naming them after something
         that is the same creature eight ways. -->
    <div class="accents">
      <button
        v-for="accent in ACCENTS"
        :key="accent"
        type="button"
        :title="accent"
        :data-accent="accent"
        :class="{ on: appearance.accent === accent }"
        @click="appearance.accent = accent"
      />
    </div>
  </div>
</template>

<style scoped>
.appearance {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.modes {
  display: flex;
  gap: 4px;
}

.modes button {
  flex: 1;
  padding: 4px 0;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--faint);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--field);
  transition: color 0.15s, border-color 0.15s;
}

.modes button:hover {
  color: var(--text);
}

.modes .on {
  color: var(--ink);
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.accents {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.accents button {
  width: 18px;
  height: 18px;
  border-radius: 2px;
  border: 1px solid rgba(var(--accent), 0.5);
  background: rgb(var(--accent));
  opacity: 0.55;
  transition: opacity 0.15s, transform 0.1s;
}

.accents button:hover {
  opacity: 0.85;
}

.accents .on {
  opacity: 1;
  box-shadow: 0 0 10px rgba(var(--accent), 0.8);
  transform: scale(1.1);
}
</style>
