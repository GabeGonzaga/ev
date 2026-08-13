<script setup lang="ts">
import { ref } from "vue";
import { useSession } from "../stores/session";

const session = useSession();
const open = ref(false);

/// How long ago, in words. The panel is glanced at, and a full timestamp is
/// something to read rather than something to see.
function ago(iso: string): string {
  const seconds = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86_400)}d`;
}

function toggle() {
  open.value = !open.value;
  if (open.value) void session.refresh();
}
</script>

<template>
  <section class="history">
    <header>
      <button type="button" class="toggle" @click="toggle()">
        <span class="chevron" :class="{ open }">›</span>
        history
      </button>
      <input
        v-if="open"
        class="find"
        type="search"
        :value="session.search"
        :placeholder="
          session.locale === 'pt-PT' ? 'procurar' : 'search what E.V. has done'
        "
        @input="
          session.search = ($event.target as HTMLInputElement).value;
          session.refresh();
        "
      />
    </header>

    <ul v-if="open">
      <li v-if="!session.entries.length" class="empty">
        {{ session.search ? `nothing matches “${session.search}”` : "nothing yet" }}
      </li>
      <li v-for="entry in session.entries" :key="entry.id">
        <span :class="entry.ok ? 'ok' : 'bad'">{{ entry.ok ? "✓" : "✕" }}</span>
        <span class="tool">{{ entry.tool }}</span>
        <span class="detail">{{ entry.speech ?? entry.error_message ?? "" }}</span>
        <time :datetime="entry.recorded_at">{{ ago(entry.recorded_at) }}</time>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.history {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--muted);
  padding: 2px 0;
}

.chevron {
  display: inline-block;
  transition: transform 0.15s;
}

.chevron.open {
  transform: rotate(90deg);
}

.find {
  flex: 1;
  min-width: 0;
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--field);
}

.find:focus {
  outline: none;
  border-color: var(--accent);
}

ul {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  overflow-y: auto;
  min-height: 0;
}

li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  border-top: 1px solid var(--line);
}

.ok { color: var(--ok); }
.bad { color: var(--bad); }

.tool {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
  flex: none;
}

.detail {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

time {
  color: var(--faint);
  flex: none;
  font-variant-numeric: tabular-nums;
}

.empty {
  color: var(--faint);
  border-top: 0;
}
</style>
