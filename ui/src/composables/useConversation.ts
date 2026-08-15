// Where the transcript comes from, which for now is nowhere.
//
// The store owns the transcript, because the state machine and the panel have
// to agree on what was said. This fills it with something to look at and
// carries the loading and failure flags the panel needs -- so the one thing
// that changes when the core is finally wired to this display is the inside
// of this file.
//
// To see the panel's failure state, give `stub` a `fails` message below. It
// is a one-word edit on purpose: an error state nobody can reach in
// development is an error state nobody has looked at.

import { storeToRefs } from "pinia";
import { onBeforeUnmount, type Ref } from "vue";
import { useAssistantState, type Turn } from "../stores/assistant";
import { stub } from "./source";

export interface Conversation {
  turns: Ref<Turn[]>;
  pending: Ref<boolean>;
  error: Ref<string | null>;
  reload: () => void;
  /// The turn has finished arriving, so it is no longer a stream. The panel
  /// is what knows -- it is the thing drawing the characters.
  settle: (id: number) => void;
}

/// A short exchange in the two languages this thing is built for, ending on
/// one that is still arriving so the streaming path is on screen rather than
/// only in the code.
const MOCK: [Turn["who"], string][] = [
  ["user", "toca o álbum Blonde"],
  ["ev", "A tocar Blonde, de Frank Ocean."],
  ["user", "what's the latency looking like"],
  ["ev", "Router 1.31 s, transcription 0.72 s. The static router took 0.005 ms."],
  ["user", "lembra-me de comprar pão amanhã às nove"],
];

const LAST =
  "Lembrete criado para amanhã às 09:00. Está guardado no Reminders, na lista predefinida.";

export function useConversation(): Conversation {
  const ev = useAssistantState();
  let timer = 0;

  const source = stub<Turn[]>(
    () => {
      ev.transcript = MOCK.map(([who, text], index) => ({
        id: index + 1,
        who,
        text,
      }));
      // Half a second behind the rest, so the panel is seen filling rather
      // than arriving complete.
      timer = window.setTimeout(() => ev.say("ev", LAST, true), 600);
      return ev.transcript;
    },
    { latency: 700 },
  );

  function settle(id: number) {
    const turn = ev.transcript.find((each) => each.id === id);
    if (turn) turn.streaming = false;
  }

  onBeforeUnmount(() => window.clearTimeout(timer));

  return {
    // The store's own ref, not a copy of the array it currently holds: the
    // store replaces that list, and a copy would keep the old one.
    turns: storeToRefs(ev).transcript as Ref<Turn[]>,
    pending: source.pending,
    error: source.error,
    reload: source.reload,
    settle,
  };
}
