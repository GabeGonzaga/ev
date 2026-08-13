<script setup lang="ts">
import { useSession } from "../stores/session";

const session = useSession();
</script>

<template>
  <!-- A question, not a notice: nothing has run, and it will not until this is
       answered. Closing the panel does not answer it, and closing it for good
       is a decline -- so the wording says what will happen, not what happened. -->
  <div v-if="session.question" class="asking">
    <div class="what">
      <strong>{{ session.question.tool }}</strong>
      <span class="risk">{{ session.question.risk }}</span>
      <code>{{ JSON.stringify(session.question.arguments) }}</code>
    </div>
    <div class="choice">
      <button type="button" class="run" @click="session.answer(true)">
        Run it
      </button>
      <button type="button" @click="session.answer(false)">Cancel</button>
    </div>
  </div>
</template>

<style scoped>
.asking {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--bad) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--bad) 35%, transparent);
}

.what {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}

.risk {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--bad);
}

code {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
  word-break: break-all;
}

.choice {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.choice button {
  padding: 5px 12px;
  border-radius: 7px;
  font-size: 13px;
  background: var(--raised);
}

.choice .run {
  background: var(--bad);
  color: #fff;
  font-weight: 600;
}
</style>
