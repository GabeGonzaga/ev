<script setup lang="ts">
// The checkered grid the whole display stands on.
//
// The same pattern in every state -- one hue, one cell size, one line weight.
// Only its intensity changes, and that is the point: the sweep can appear to
// *paint* it in because the pattern is already there at a tenth of its
// brightness, waiting. Two different grids fading into each other would be a
// cross-dissolve, which reads as a slide change rather than as light moving
// across a surface.
//
// Brightest under the middle and gone before the edges, by a radial mask
// rather than an overlay, so nothing drawn on top of it is dimmed by it.
//
// CSS gradients: this never changes except in intensity, so it should cost
// nothing to keep on screen.

withDefaults(
  defineProps<{
    /// 0 for the idle wash, 1 for the awake grid. The sweep drives it.
    lit?: number;
    /// How much has been painted in, top to bottom, 0..1. At rest it is 1 and
    /// the mask is a no-op. A mask rather than an opacity, so the band
    /// uncovers the pattern instead of turning it up.
    painted?: number;
  }>(),
  { lit: 0, painted: 1 },
);
</script>

<template>
  <div class="mesh" :style="{ '--lit': lit, '--painted': painted }" aria-hidden="true">
    <div class="squares idle" />
    <div class="squares awake" />
  </div>
</template>

<style scoped>
.mesh {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  /* Everything above the band is drawn; below it, not yet. The soft edge is
     the band catching the pattern as it passes. Measured against 100% plus
     the ramp's own width, so a finished screen has no ramp left on it. */
  -webkit-mask-image: linear-gradient(
    to bottom,
    #000 calc(var(--painted) * (100% + 90px) - 90px),
    transparent calc(var(--painted) * (100% + 90px))
  );
  mask-image: linear-gradient(
    to bottom,
    #000 calc(var(--painted) * (100% + 90px) - 90px),
    transparent calc(var(--painted) * (100% + 90px))
  );
}

.squares {
  position: absolute;
  inset: 0;
  background-image:
    repeating-linear-gradient(
      0deg,
      currentColor 0 1px,
      transparent 1px var(--grid-cell)
    ),
    repeating-linear-gradient(
      90deg,
      currentColor 0 1px,
      transparent 1px var(--grid-cell)
    );
  /* Sharpest in the middle, gone well before the edges, so the centre reads
     as the focal point rather than as the middle of a wallpaper. */
  -webkit-mask-image: radial-gradient(
    62% 62% at 50% 48%,
    #000 0%,
    rgba(0, 0, 0, 0.55) 45%,
    transparent 78%
  );
  mask-image: radial-gradient(
    62% 62% at 50% 48%,
    #000 0%,
    rgba(0, 0, 0, 0.55) 45%,
    transparent 78%
  );
}

/* Two copies of one pattern, cross-faded by `--lit`. Same cell, same phase,
   so what changes is only how much light is in it. */
.idle {
  color: var(--grid-idle);
  opacity: calc(1 - var(--lit));
}

.awake {
  color: var(--grid-awake);
  opacity: var(--lit);
}
</style>
