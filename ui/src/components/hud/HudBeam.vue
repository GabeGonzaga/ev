<script setup lang="ts">
// The scan line that uncovers the instrument.
//
// It is not a decoration laid over the transition -- it is the transition.
// The same number that puts the beam at a height also says how much of the
// grid and the chrome have been revealed, so the beam cannot drift out of
// step with what it is supposed to be uncovering. There is one number and
// three things read it.
//
// Positioned with a transform against the viewport height rather than `top`,
// because this moves every frame for six hundred milliseconds and `top` would
// have the compositor redoing layout for all of them.

defineProps<{
  /// 0 at the top edge, 1 at the bottom.
  at: number;
}>();
</script>

<template>
  <div class="beam" :style="{ '--at': at }" aria-hidden="true" />
</template>

<style scoped>
.beam {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 3px;
  background: var(--neon-bright);
  box-shadow:
    0 0 10px rgba(143, 203, 255, 0.85),
    0 0 34px rgba(61, 155, 255, 0.5);
  transform: translate3d(0, calc(var(--at) * 100dvh), 0);
  will-change: transform;
  z-index: 4;
  pointer-events: none;
}

/* The trail, above the line because the line is travelling down: what is
   behind a moving thing is where it has been. */
.beam::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  height: 120px;
  background: linear-gradient(
    to bottom,
    transparent,
    rgba(61, 155, 255, 0.06) 45%,
    rgba(143, 203, 255, 0.28)
  );
}
</style>
