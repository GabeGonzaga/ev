// What the core says, arriving at the display.
//
// The stage machine could always wake; nothing had ever told it to. The core
// has heard its own name since the wake loop landed, the app has emitted
// `wake.woken` the whole time, and this display answered only to the
// spacebar -- so the name worked everywhere except on the screen built for
// it. This is the wire, and it is the whole of it.
//
// One direction only. The core says what happened and the display arranges
// itself; nothing here sends anything back, because everything that acts goes
// through `Registry.call()` and a display is not a caller.
//
// In a browser there is no app to listen to, and every subscription here
// quietly does nothing -- which is correct: a page cannot hold a global
// hotkey or a wake loop, and must not draw itself as though it could.

import { onMounted } from "vue";
import * as api from "../api";
import { useAssistantState } from "../stores/assistant";

export function useWakeSignals(): void {
  const ev = useAssistantState();

  onMounted(() => {
    void api.onListening(
      // The wake loop's microphone, while it is open -- which is all day, if
      // the name is on. Invariant 8 asks for a visible active state, and this
      // is the fact the dock's microphone lights from. It is deliberately not
      // `voice`: a room being listened to for two syllables is not E.V.
      // listening to a request, and drawing them the same would make the one
      // that matters unreadable.
      (live) => {
        ev.hearing = live;
      },
      // The name, and nothing after it yet. Somebody is about to speak.
      () => {
        ev.triggerWake();
        ev.voice = "listening";
      },
    );

    void api.onHotkeyTurn(
      // A turn this window did not start: the key held anywhere on the
      // machine, or the utterance that followed the name. Either way the
      // display should already be awake when the words arrive.
      () => {
        ev.triggerWake();
        ev.voice = "listening";
      },
      (result) => {
        ev.voice = "idle";
        if (!result) return;

        if (result.heard) ev.say("user", result.heard);
        for (const line of result.spoken ?? []) ev.say("ev", line);
        // A turn that failed says so on the display rather than in a console
        // nobody has open.
        if (result.error) ev.error = result.error;
      },
    );

    // The lens, while it is on. The same reasoning as the microphone: macOS
    // shows an indicator, and an indicator belonging to the system does not
    // say which application turned the camera on.
    void api.onCamera((live) => {
      ev.looking = live;
    });
  });
}
