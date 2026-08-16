<script setup lang="ts">
// The checkered grid the whole display stands on.
//
// One pattern at two intensities, always drawn. Idle is near-invisible; awake
// is the neon level; and the sweep is not a fade between them but a *line*
// between them -- the band is the boundary, with the awake grid behind it and
// the idle grid ahead of it. That is what makes the light look like it is
// painting the squares in rather than turning a dimmer up.
//
// Which also means the grid is never absent. Reference 1 has the faint
// checker across the whole screen while the display is only idling; it is the
// floor, not a thing that arrives.
//
// Brightest under the middle and gone before the edges, by a radial mask
// rather than an overlay, so nothing drawn on top of it is dimmed by it.

withDefaults(
  defineProps<{
    /// Where the band is, 0 at the top edge, 1 past the bottom. Everything
    /// above it has been painted; everything below it has not.
    painted?: number;
    /// No band: cross-fade the two intensities instead. What the machine gets
    /// when it has asked for less motion.
    calm?: boolean;
  }>(),
  { painted: 0, calm: false },
);
</script>

<template>
  <div class="mesh" :class="{ calm }" :style="{ '--painted': painted }" aria-hidden="true">
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

.idle {
  color: var(--grid-idle);
}

.awake {
  color: var(--grid-awake);
}

/* The band is the boundary. Behind it (above), the awake grid; ahead of it,
   the idle one. Two masks that are each other's inverse, sharing one number,
   so a gap between them is not expressible.

   The ramp is measured against 100% plus its own width, so a finished sweep
   leaves no soft edge sitting on the bottom of the screen. */
.mesh:not(.calm) .awake {
  -webkit-mask-image: linear-gradient(
      to bottom,
      #000 calc(var(--painted) * (100% + 90px) - 90px),
      transparent calc(var(--painted) * (100% + 90px))
    ),
    radial-gradient(62% 62% at 50% 48%, #000 0%, rgba(0, 0, 0, 0.55) 45%, transparent 78%);
  -webkit-mask-composite: source-in;
  mask-image: linear-gradient(
      to bottom,
      #000 calc(var(--painted) * (100% + 90px) - 90px),
      transparent calc(var(--painted) * (100% + 90px))
    ),
    radial-gradient(62% 62% at 50% 48%, #000 0%, rgba(0, 0, 0, 0.55) 45%, transparent 78%);
  mask-composite: intersect;
}

.mesh:not(.calm) .idle {
  -webkit-mask-image: linear-gradient(
      to bottom,
      transparent calc(var(--painted) * (100% + 90px) - 90px),
      #000 calc(var(--painted) * (100% + 90px))
    ),
    radial-gradient(62% 62% at 50% 48%, #000 0%, rgba(0, 0, 0, 0.55) 45%, transparent 78%);
  -webkit-mask-composite: source-in;
  mask-image: linear-gradient(
      to bottom,
      transparent calc(var(--painted) * (100% + 90px) - 90px),
      #000 calc(var(--painted) * (100% + 90px))
    ),
    radial-gradient(62% 62% at 50% 48%, #000 0%, rgba(0, 0, 0, 0.55) 45%, transparent 78%);
  mask-composite: intersect;
}

/* Asked for less motion: no band, no boundary travelling down the screen --
   the two intensities simply cross-fade where they stand. */
.mesh.calm .awake {
  opacity: var(--painted);
}

.mesh.calm .idle {
  opacity: calc(1 - var(--painted));
}
</style>
