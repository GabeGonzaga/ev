<script setup lang="ts">
import { computed } from "vue";
import { useSession } from "../stores/session";

const session = useSession();
const emit = defineEmits<{ pick: [string] }>();

/// The one place the interface admits it is software you can point at. Kept
/// visually subordinate to the orb -- smaller, dimmer, lower contrast -- so
/// the idle screen still reads as "the orb, with some shortcuts beneath it".
const GLYPHS = {
  globe: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M3 12h18 M12 3c2.5 2.6 2.5 15.4 0 18 M12 3c-2.5 2.6-2.5 15.4 0 18",
  note: "M9 18V6l10-2v12 M9 18a3 3 0 1 1-6 0a3 3 0 0 1 6 0 M19 16a3 3 0 1 1-6 0a3 3 0 0 1 6 0",
  pen: "M4 20l4-1 10-10-3-3L5 16z M14 6l3 3",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M12 7v5l3 2",
} as const;

const TILES: Record<
  string,
  { glyph: keyof typeof GLYPHS; label: string; says: string }[]
> = {
  "pt-PT": [
    { glyph: "globe", label: "github", says: "abre o github" },
    { glyph: "note", label: "tocar", says: "toca o artista Kendrick" },
    { glyph: "pen", label: "nota", says: "cria uma nota chamada Compras" },
    { glyph: "clock", label: "lembrete", says: "lembra-me de comprar pão" },
  ],
  en: [
    { glyph: "globe", label: "github", says: "open github" },
    { glyph: "note", label: "play", says: "play the artist Kendrick" },
    { glyph: "pen", label: "note", says: "make a note called Shopping" },
    { glyph: "clock", label: "remind", says: "remind me to call the dentist" },
  ],
};

const tiles = computed(() => TILES[session.locale] ?? TILES.en);
</script>

<template>
  <div class="tiles">
    <button
      v-for="tile in tiles"
      :key="tile.label"
      type="button"
      :title="tile.says"
      @click="emit('pick', tile.says)"
    >
      <span class="glyph">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path :d="GLYPHS[tile.glyph]" />
        </svg>
      </span>
      <span class="label">{{ tile.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.tiles {
  display: flex;
  gap: 24px;
  justify-content: center;
}

button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.glyph {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 12px;
  color: rgba(var(--tick), 0.7);
  background: rgba(var(--tick), 0.08);
  border: 1px solid rgba(var(--tick), 0.15);
  transition: background 0.15s, color 0.15s;
}

.label {
  font-family: var(--terminal);
  font-size: 11px;
  color: rgba(var(--tick), 0.6);
  transition: color 0.15s;
}

.glyph svg {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

button:hover .glyph {
  background: rgba(var(--tick), 0.16);
  color: var(--text);
}

button:hover .label {
  color: rgba(242, 245, 248, 0.9);
}
</style>
