// What E.V. is doing, and what the display should therefore look like.
//
// One store for the whole HUD. The surface, the orb, the chrome and every
// panel read the same state out of here, because a display whose parts each
// keep their own idea of what is happening will eventually show two of them
// at once.
//
// Nothing here talks to the core. The wake word, the transcript and the audio
// level are all stubs -- see `triggerWake` -- and the seam is deliberately
// narrow so that replacing them is one function each.

import { defineStore } from "pinia";
import { computed, ref } from "vue";

/// IDLE      waiting to be called; the clock and the orb, nothing else
/// WAKING    the ~900ms reveal; the beam is crossing the screen
/// ACTIVE    the HUD is up and nothing is being said
/// LISTENING taking an utterance
/// THINKING  routing it
/// SPEAKING  answering
export type AssistantState =
  | "IDLE"
  | "WAKING"
  | "ACTIVE"
  | "LISTENING"
  | "THINKING"
  | "SPEAKING";

export type PanelName =
  | "conversation"
  | "camera"
  | "media"
  | "web"
  | "headlines"
  | "chart";

export interface Turn {
  id: number;
  who: "user" | "ev";
  text: string;
  /// True while the text is still arriving, which is what earns the cursor.
  streaming?: boolean;
}

/// How long the reveal takes, and how long undoing it takes. Undoing is
/// faster: leaving a screen should never feel like a ceremony.
export const WAKE_MS = 900;
export const SLEEP_MS = 500;

/// Back to IDLE after a minute and a half of nothing. Long enough to read an
/// answer and think about it, short enough that a room left alone goes dark.
export const IDLE_AFTER_MS = 90_000;

export const useAssistantState = defineStore("assistant", () => {
  const state = ref<AssistantState>("IDLE");
  const transcript = ref<Turn[]>([]);
  /// 0..1, smoothed by whoever writes it. The orb reads this and nothing else.
  const audioLevel = ref(0);
  const error = ref<string | null>(null);
  const activePanels = ref<PanelName[]>([
    "conversation",
    "camera",
    "media",
    "web",
    "headlines",
    "chart",
  ]);

  /// Awake covers every state that is not the clock: the HUD is on screen and
  /// the chrome is drawn. WAKING is included because the beam is revealing it.
  const awake = computed(() => state.value !== "IDLE");
  /// Busy means a turn is in flight, and a turn in flight is not idle no
  /// matter how long since the last key was pressed.
  const busy = computed(() =>
    ["LISTENING", "THINKING", "SPEAKING"].includes(state.value),
  );

  let waking = 0;
  let idling = 0;

  /// Something happened, so the idle countdown starts again. Called by the
  /// surface on any input and by every transition below.
  function touch() {
    window.clearTimeout(idling);
    if (state.value === "IDLE") return;
    idling = window.setTimeout(() => {
      // A turn that is still running is not an idle screen.
      if (busy.value) return touch();
      sleep();
    }, IDLE_AFTER_MS);
  }

  /// The wake word, stubbed. Bound to the spacebar by the surface until the
  /// core's own wake loop is wired to it -- the core already hears the name;
  /// this store is not yet listening to the core.
  function triggerWake() {
    if (state.value !== "IDLE") return;
    error.value = null;
    state.value = "WAKING";
    window.clearTimeout(waking);
    waking = window.setTimeout(() => {
      state.value = "ACTIVE";
      touch();
    }, WAKE_MS);
  }

  function sleep() {
    window.clearTimeout(waking);
    window.clearTimeout(idling);
    state.value = "IDLE";
    audioLevel.value = 0;
  }

  /// The three working states, and the way back to ACTIVE. Separate functions
  /// rather than one setter: a state machine whose transitions are all
  /// `state = x` is not a state machine, it is a variable.
  function listen() {
    if (!awake.value) return;
    state.value = "LISTENING";
    touch();
  }

  function think() {
    if (!awake.value) return;
    state.value = "THINKING";
    touch();
  }

  function speak() {
    if (!awake.value) return;
    state.value = "SPEAKING";
    touch();
  }

  function settle() {
    if (!awake.value) return;
    state.value = "ACTIVE";
    touch();
  }

  function togglePanel(name: PanelName) {
    activePanels.value = activePanels.value.includes(name)
      ? activePanels.value.filter((panel) => panel !== name)
      : [...activePanels.value, name];
    touch();
  }

  function say(who: Turn["who"], text: string, streaming = false): Turn {
    const turn: Turn = { id: transcript.value.length + 1, who, text, streaming };
    transcript.value = [...transcript.value, turn];
    touch();
    return turn;
  }

  return {
    state,
    transcript,
    audioLevel,
    error,
    activePanels,
    awake,
    busy,
    triggerWake,
    sleep,
    listen,
    think,
    speak,
    settle,
    togglePanel,
    say,
    touch,
  };
});
