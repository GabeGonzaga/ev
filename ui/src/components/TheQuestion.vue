<script setup lang="ts">
import { computed } from "vue";
import { useSession } from "../stores/session";

const session = useSession();

/// Whether this question can be answered here at all.
///
/// `verify` means macOS has to establish who is at the machine, and a button
/// in a window E.V. drew cannot do that. A surface that cannot satisfy it says
/// so rather than offering a yes that would mean something weaker.
const answerable = computed(
  () => !session.question || ["none", "ack"].includes(session.question.assurance),
);

const what = computed(() =>
  Object.entries(session.question?.arguments ?? {})
    .filter(([, value]) => value !== null && value !== "")
    .map(([name, value]) => `${name}: ${value}`)
    .join("   "),
);
</script>

<template>
  <!-- A question, not a notice: nothing has run, and it will not until this is
       answered. Closing the panel does not answer it. -->
  <div v-if="session.question" class="asking">
    <p class="what">
      <strong>{{ session.question.tool }}</strong>
      <span v-if="session.question.application" class="app">
        {{ session.question.application }}
      </span>
      <span class="risk">{{ session.question.risk }}</span>
    </p>
    <p v-if="what" class="args">{{ what }}</p>

    <template v-if="answerable">
      <div class="choice">
        <button type="button" class="run" @click="session.answer(true)">
          Allow once
        </button>
        <button
          v-if="session.question.application"
          type="button"
          @click="session.answer(true, 'open')"
        >
          Always allow {{ session.question.application }}
        </button>
        <button type="button" @click="session.answer(false)">Not now</button>
        <button
          v-if="session.question.application"
          type="button"
          class="never"
          @click="session.answer(false, 'blocked')"
        >
          Never
        </button>
      </div>
    </template>

    <p v-else class="cannot">
      {{ session.question.application }} is set to verify, and this window
      cannot ask macOS to check who you are. Lower it with
      <code>ev --app {{ session.question.application }} ask</code>.
    </p>
  </div>
</template>

<style scoped>
.asking {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--bad) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--bad) 35%, transparent);
}

.what {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}

.app {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--raised);
  font-size: 12px;
}

.risk {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--bad);
}

.args {
  margin: 0;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
  word-break: break-word;
}

.choice {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.choice button {
  padding: 5px 11px;
  border-radius: 7px;
  font-size: 12px;
  background: var(--raised);
}

.choice .run {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}

.choice .never {
  color: var(--bad);
}

.cannot {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

code {
  font-family: var(--mono);
  font-size: 11px;
}
</style>
