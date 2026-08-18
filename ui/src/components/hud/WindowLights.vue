<script setup lang="ts">
// Close, minimise, zoom -- the window's own three, where macOS puts them.
//
// The HUD replaced a view that had these and did not bring them along, so
// since then there has been no way to close or minimise the window from the
// display at all: only the menu bar item, which is not where anybody looks
// for a close button.
//
// Squared rather than round, because everything else here is, and the colours
// are macOS's so the muscle memory works without the shape having to match.
// The glyph appears on hover over the group, as it does natively.

import { hasWindowControls, windowControl } from "../../api";
import { t } from "../../i18n";
</script>

<template>
  <div v-if="hasWindowControls" class="lights">
    <button
      class="close"
      type="button"
      :title="t('window.close')"
      @click="windowControl('close')"
    />
    <button
      class="minimise"
      type="button"
      :title="t('window.minimise')"
      @click="windowControl('minimise')"
    />
    <button
      class="zoom"
      type="button"
      :title="t('window.zoom')"
      @click="windowControl('fullscreen')"
    />
  </div>
</template>

<style scoped>
.lights {
  position: absolute;
  /* Inside the corner bracket and clear of the left-edge ruler, which are
     already at 10 and 14. */
  top: 15px;
  left: 34px;
  display: flex;
  gap: 7px;
  z-index: 5;
}

button {
  position: relative;
  width: 11px;
  height: 11px;
  padding: 0;
  border: 1px solid rgba(0, 0, 0, 0.35);
  border-radius: 1px;
  opacity: 0.85;
  transition: opacity 0.15s;
}

.lights:hover button {
  opacity: 1;
}

.close {
  background: #ff5f57;
}

.minimise {
  background: #ffbd2e;
}

.zoom {
  background: #27c93f;
}

/* The glyphs, on hover over the group -- the same as macOS, and the reason
   the colours alone are enough the rest of the time. */
button::after {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-family: var(--mono);
  font-size: 9px;
  line-height: 1;
  color: rgba(0, 0, 0, 0.55);
  opacity: 0;
  transition: opacity 0.15s;
}

.lights:hover button::after {
  opacity: 1;
}

.close::after {
  content: "\00d7";
}

.minimise::after {
  content: "\2013";
}

.zoom::after {
  content: "\002b";
}
</style>
