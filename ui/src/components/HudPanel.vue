<script setup lang="ts">
defineProps<{ label: string; live?: boolean }>();
</script>

<template>
  <!-- One widget. Squared, bracketed at two corners, lit at the edge when
       something in it is happening. -->
  <section class="hud" :class="{ live }">
    <header>
      {{ label }}
      <slot name="aside" />
    </header>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  flex: 1;
}

.live {
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}
</style>
