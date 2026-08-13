<script setup lang="ts">
import { useSession } from "../stores/session";

const session = useSession();

/// How long ago, in words. A panel is glanced at, and a full timestamp is
/// something to read rather than something to see.
function ago(iso: string): string {
  const seconds = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86_400)}d`;
}

function search(value: string) {
  session.search = value;
  void session.refresh();
}
</script>

<template>
  <div class="trail">
    <input
      class="find"
      type="search"
      :value="session.search"
      :placeholder="session.locale === 'pt-PT' ? 'procurar' : 'search'"
      @input="search(($event.target as HTMLInputElement).value)"
    />

    <ul>
      <li v-if="!session.entries.length" class="empty">
        {{ session.search ? `nothing matches “${session.search}”` : "nothing yet" }}
      </li>
      <li v-for="entry in session.entries" :key="entry.id">
        <span :class="entry.ok ? 'ok' : 'bad'">{{ entry.ok ? "▸" : "✕" }}</span>
        <span class="tool">{{ entry.tool }}</span>
        <span class="detail">{{ entry.speech ?? entry.error_message ?? "" }}</span>
        <time :datetime="entry.recorded_at">{{ ago(entry.recorded_at) }}</time>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.trail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  flex: 1;
}

.find {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 8px;
  font-family: var(--mono);
  font-size: 11px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--field);
}

.find:focus {
  outline: none;
  border-color: var(--panel-lit);
  box-shadow: var(--glow);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  min-height: 0;
  flex: 1;
}

li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 0;
  font-size: 11.5px;
  border-bottom: 1px solid var(--line);
}

.ok { color: var(--ink); }
.bad { color: var(--bad); }

.tool {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  flex: none;
}

.detail {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}

time {
  color: var(--faint);
  font-family: var(--mono);
  font-size: 10px;
  flex: none;
}

.empty {
  color: var(--faint);
  border-bottom: 0;
}
</style>
