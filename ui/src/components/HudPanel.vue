<script setup lang="ts">
import { computed } from "vue";
import { useLayout } from "../stores/layout";

const props = defineProps<{ label: string; live?: boolean }>();

const layout = useLayout();
const folded = computed(() => layout.isFolded(props.label));
const focused = computed(() => layout.focused === props.label);
</script>

<template>
  <!-- One widget. Squared, bracketed at two corners, lit at the edge when
       something in it is happening. Folded it is just its own title bar,
       which is the smallest honest thing a widget can be. -->
  <section class="hud" :class="{ live, folded, focused }">
    <header>
      <button class="name" type="button" @click="layout.fold(label)">
        {{ label }}
      </button>
      <slot name="aside" />
      <span class="rule" />
      <button
        class="control"
        type="button"
        :title="folded ? 'unfold' : 'fold'"
        @click="layout.fold(label)"
      >
        {{ folded ? "▸" : "▾" }}
      </button>
      <button
        class="control"
        type="button"
        :title="focused ? 'back' : 'fill the display'"
        @click="layout.focus(label)"
      >
        {{ focused ? "▪" : "▫" }}
      </button>
    </header>

    <div v-if="!folded" class="body">
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

.folded {
  flex: none;
}

.live {
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

.name {
  font: inherit;
  letter-spacing: inherit;
  /* `font:` resets it, so the header's casing has to be asked for again. */
  text-transform: inherit;
  color: inherit;
  padding: 0;
}

.name:hover,
.control:hover {
  color: var(--ink);
}

.rule {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--line), transparent);
}

.control {
  font-size: 10px;
  line-height: 1;
  color: var(--faint);
  padding: 2px 3px;
}
</style>
