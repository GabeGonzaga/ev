<script setup lang="ts">
// The floor the HUD stands on: a grid that recedes.
//
// Two planes rather than one. Flat, it is graph paper; tilted only, it is a
// racing game. Together -- a faint flat mesh across the whole screen with a
// tilted one running away from the bottom edge -- it reads as depth without
// anybody having to notice why.
//
// CSS gradients, not SVG and not canvas: this never changes except during the
// reveal, so it should cost nothing to keep on screen.

withDefaults(
  defineProps<{
    /// How much of the grid has been revealed, 0..1, top to bottom. The scan
    /// beam drives this during WAKING; at rest it is 1 and the mask is a
    /// no-op. It is a mask rather than an opacity so the beam can appear to
    /// uncover the mesh rather than turn it up.
    reveal?: number;
  }>(),
  { reveal: 1 },
);
</script>

<template>
  <div class="mesh" :style="{ '--reveal': reveal }" aria-hidden="true">
    <div class="flat" />
    <div class="floor" />
  </div>
</template>

<style scoped>
.mesh {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  /* Everything above the beam is drawn; everything below it is not yet. The
     soft edge is the beam's own trail catching the mesh as it passes. */
  -webkit-mask-image: linear-gradient(
    to bottom,
    #000 calc(var(--reveal) * 100% - 90px),
    transparent calc(var(--reveal) * 100%)
  );
  mask-image: linear-gradient(
    to bottom,
    #000 calc(var(--reveal) * 100% - 90px),
    transparent calc(var(--reveal) * 100%)
  );
}

.flat,
.floor {
  position: absolute;
  background-image:
    repeating-linear-gradient(0deg, var(--hud-line) 0 1px, transparent 1px 48px),
    repeating-linear-gradient(90deg, var(--hud-line) 0 1px, transparent 1px 48px);
}

/* The mesh over everything, faint enough to be texture rather than pattern. */
.flat {
  inset: 0;
  opacity: 0.55;
  -webkit-mask-image: radial-gradient(120% 90% at 50% 40%, #000 30%, transparent 85%);
  mask-image: radial-gradient(120% 90% at 50% 40%, #000 30%, transparent 85%);
}

/* And the floor, running off toward a horizon that is off-screen. Anchored
   to the bottom so the tilt costs nothing at the top of the display. */
.floor {
  left: -40%;
  right: -40%;
  bottom: -6%;
  height: 58%;
  /* Compressed by the tilt, so it needs a stronger line than the flat mesh
     to arrive at the same weight on screen. */
  background-image:
    repeating-linear-gradient(0deg, rgba(120, 180, 255, 0.3) 0 1px, transparent 1px 48px),
    repeating-linear-gradient(90deg, rgba(120, 180, 255, 0.3) 0 1px, transparent 1px 48px);
  transform: perspective(760px) rotateX(70deg);
  transform-origin: 50% 100%;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(to bottom, transparent, #000 55%);
  mask-image: linear-gradient(to bottom, transparent, #000 55%);
}
</style>
