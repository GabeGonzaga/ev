// What the display is showing, and what E.V. is doing.
//
// Two axes, deliberately separate. The **stage** is where the interface is:
// blank, idle, waking, awake, ambient. The **voice** is what E.V. is doing
// inside whatever stage that is: listening, thinking, speaking. They are not
// the same question -- E.V. can be listening on the awake ring or on the
// ambient orb, and the display should answer both without one state having to
// enumerate the other.
//
// Working is not stored. A display is working when it is awake and something
// is open on it, which is a fact about the widgets rather than a fifth thing
// to keep in sync with them.
//
// Nothing here talks to the core yet. The wake word is a stub -- see
// `triggerWake` -- and the seam is narrow on purpose.

import { defineStore } from "pinia";
import { computed, ref } from "vue";

/// blank   the grid and nothing else; the empty stage
/// idle    the thin white ring, arcs turning, waiting to be called
/// waking  the sweep, once, ~700-900ms
/// awake   the neon ring, crown and dock: "I'm listening"
/// ambient the plasma orb and the clock; a bedside presence
export type Stage = "blank" | "idle" | "waking" | "awake" | "ambient";

/// Where the camera is showing, if it is.
///
/// Not a stage: full screen, the feed is the display's *background* -- the
/// grid still runs over it, the chrome still frames it and the ring still
/// turns in the corner. A stage would have replaced all of that, which is the
/// opposite of what a background is.
export type Lens = "off" | "window" | "full";

/// What E.V. is doing, which the core drives and the ring reflects.
export type Voice = "idle" | "listening" | "thinking" | "speaking";

/// The things that can be open on the display. Deliberately short: the spec
/// forbids news and market widgets, because both would mean fetching from the
/// internet.
export type Widget = "console" | "music" | "shortcuts" | "add";

/// The wide ones. Only these push the core out of the middle: a window big
/// enough to want the centre gets it, and everything else is small enough to
/// sit beside a core that has simply made room.
const WIDE: readonly Widget[] = ["shortcuts"];

export interface Turn {
  id: number;
  who: "user" | "ev";
  text: string;
  /// True while the text is still arriving, which is what earns the cursor.
  streaming?: boolean;
}

/// The sweep, and undoing it. Undoing is faster: leaving a screen should
/// never feel like a ceremony.
export const WAKE_MS = 820;
export const SLEEP_MS = 480;

/// How long the core takes to drift to the edge and back.
export const DRIFT_MS = 500;

/// Back to idle after a minute and a half of nothing. Long enough to read an
/// answer and think about it, short enough that a room left alone goes quiet.
export const IDLE_AFTER_MS = 90_000;

export const useAssistantState = defineStore("assistant", () => {
  const stage = ref<Stage>("idle");
  const voice = ref<Voice>("idle");
  const open = ref<Widget[]>([]);
  const transcript = ref<Turn[]>([]);
  /// 0..1, raw. The ring and the orb smooth it themselves.
  const audioLevel = ref(0);
  const error = ref<string | null>(null);
  /// The language E.V. answers in, which is also the language its display
  /// writes dates and speaks back in. Settings will own this when the display
  /// is wired to the core; pt-PT is the project's default until then.
  const locale = ref("pt-PT");
  /// The lens, while it is on. Invariant 8 wants a visible active state, and
  /// the dock is where it is visible.
  const looking = ref(false);
  const lens = ref<Lens>("off");
  /// Which way it was last shown, so turning it on again gives back what was
  /// last chosen rather than always the same one.
  const lastLens = ref<Exclude<Lens, "off">>("full");

  /// Awake and something open on it.
  const working = computed(() => stage.value === "awake" && open.value.length > 0);

  /// A wide window is up, so the core leaves the middle for it.
  const aside = computed(
    () => working.value && open.value.some((each) => WIDE.includes(each)),
  );

  /// Something narrow is up. The core stays where it is and only makes
  /// itself smaller -- moving it to the edge for a 400px panel is a lot of
  /// travel to free room nobody needed, and it leaves the middle of the
  /// display as somewhere windows can be dragged through.
  const tucked = computed(() => working.value && !aside.value);

  /// Whether the ring is on screen at all -- ambient replaces it with the orb,
  /// blank has nothing.
  const ringed = computed(() =>
    ["idle", "waking", "awake"].includes(stage.value),
  );

  /// The core never leaves the screen. With the feed behind everything it
  /// shrinks into the corner and keeps turning; it does not go away, because
  /// a display where E.V. has vanished is a display that has stopped.
  const badged = computed(() => lens.value === "full");

  /// A turn is in flight. Not idle however long since the last key.
  const busy = computed(() => voice.value !== "idle");

  let waking = 0;
  let idling = 0;

  /// Something happened, so the countdown back to idle starts again.
  function touch() {
    window.clearTimeout(idling);
    if (stage.value !== "awake") return;
    idling = window.setTimeout(() => {
      // A turn still running is not an idle screen, and neither is a display
      // with something open on it.
      if (busy.value || open.value.length) return touch();
      rest();
    }, IDLE_AFTER_MS);
  }

  /// The name, or the hotkey. Stubbed until the core's own wake loop reaches
  /// this store -- the core already hears the name; this does not yet listen
  /// to the core.
  function triggerWake() {
    if (stage.value === "waking" || stage.value === "awake") return;
    error.value = null;
    stage.value = "waking";
    window.clearTimeout(waking);
    waking = window.setTimeout(() => {
      stage.value = "awake";
      touch();
    }, WAKE_MS);
  }

  /// Back to the thin white ring. The glow fades out rather than cutting.
  function rest() {
    window.clearTimeout(waking);
    window.clearTimeout(idling);
    stage.value = "idle";
    voice.value = "idle";
    audioLevel.value = 0;
  }

  /// The bedside presence: orb and clock, nothing else.
  function sleep() {
    window.clearTimeout(waking);
    window.clearTimeout(idling);
    stage.value = "ambient";
    open.value = [];
  }

  /// Show the camera, one way or the other, or stop showing it.
  function watch_(how: Lens) {
    if (how !== "off") {
      if (stage.value !== "awake") triggerWake();
      lastLens.value = how;
    }
    lens.value = how;
    if (how === "off") looking.value = false;
    touch();
  }

  /// What the dock's camera icon does: on to whichever way it was last shown,
  /// and off from either of them.
  function toggleLens() {
    watch_(lens.value === "off" ? lastLens.value : "off");
  }

  /// The clean screen: the grid on its own.
  function clear() {
    stage.value = stage.value === "blank" ? "idle" : "blank";
    open.value = [];
  }

  function show(widget: Widget) {
    if (stage.value !== "awake") triggerWake();
    if (!open.value.includes(widget)) open.value = [...open.value, widget];
    touch();
  }

  function hide(widget: Widget) {
    open.value = open.value.filter((each) => each !== widget);
    touch();
  }

  function toggle(widget: Widget) {
    if (open.value.includes(widget)) hide(widget);
    else show(widget);
  }

  function isOpen(widget: Widget): boolean {
    return open.value.includes(widget);
  }

  function say(who: Turn["who"], text: string, streaming = false): Turn {
    const turn: Turn = { id: transcript.value.length + 1, who, text, streaming };
    transcript.value = [...transcript.value, turn];
    touch();
    return turn;
  }

  return {
    stage,
    voice,
    locale,
    looking,
    open,
    transcript,
    audioLevel,
    error,
    working,
    aside,
    tucked,
    ringed,
    badged,
    lens,
    watch: watch_,
    toggleLens,
    busy,
    triggerWake,
    rest,
    sleep,
    clear,
    show,
    hide,
    toggle,
    isOpen,
    say,
    touch,
  };
});
