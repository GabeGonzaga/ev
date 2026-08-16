// What Music is playing, for the widget to draw.
//
// A front end, and only a front end: every button submits the sentence a
// person would have said, and the core routes and authorises it exactly as it
// does a spoken one. Nothing here talks to Music -- it asks E.V. to, and is
// told what happened.
//
// The clock between reads is local. Music is asked every few seconds and the
// progress line is advanced from the last answer in between, because a bar
// that only moves when a poll lands stutters, and polling fast enough to hide
// that is polling for the sake of the bar.

import { onBeforeUnmount, ref, type Ref } from "vue";
import { submit } from "../api";

export interface Playing {
  state: "playing" | "paused" | "stopped" | string;
  track: string;
  artist: string;
  album: string;
  at: number;
  length: number;
  shuffle: boolean;
  repeat: "off" | "all" | "one" | string;
  cover: string | null;
  /// Whatever the file carries, which for a streamed track is nothing.
  lyrics: string;
}

export interface NowPlaying {
  playing: Ref<Playing | null>;
  pending: Ref<boolean>;
  error: Ref<string | null>;
  /// Seconds in, advanced locally between reads.
  at: Ref<number>;
  read: () => Promise<void>;
  /// Say something to the core, then read what it did.
  tell: (what: string) => Promise<void>;
}

/// Often enough to notice a track change, rarely enough that the five-minute
/// verification window is not the thing anybody remembers about this widget.
const EVERY_MS = 4000;

export function useNowPlaying(locale: () => string): NowPlaying {
  const playing = ref<Playing | null>(null);
  const pending = ref(true);
  const error = ref<string | null>(null);
  const at = ref(0);

  let ticking = 0;
  let polling = 0;

  async function read() {
    try {
      const answer = await submit("now playing", locale());
      const data = answer.data as unknown as Playing | undefined;
      if (!data || typeof data.state !== "string") {
        // A refusal comes back as a turn like any other: the policy declined,
        // or the core did not understand. Say which rather than showing an
        // empty player.
        error.value = answer.error || answer.speech || `no answer: ${answer.outcome}`;
        return;
      }
      playing.value = data;
      at.value = data.at;
      error.value = null;
    } catch (trouble) {
      error.value = String(trouble instanceof Error ? trouble.message : trouble);
    } finally {
      pending.value = false;
    }
  }

  async function tell(what: string) {
    await submit(what, locale());
    // Music answers a read before it has finished moving, so the first look
    // after a command can still be the previous track -- the same race the
    // adapter documents. A short wait costs nothing here.
    window.setTimeout(read, 250);
  }

  // One interval for the reads, one for the second hand. Neither is the
  // shared frame loop: this is a clock, not an animation, and waking sixty
  // times a second to move a bar one pixel is the wrong trade.
  polling = window.setInterval(read, EVERY_MS);
  ticking = window.setInterval(() => {
    if (playing.value?.state !== "playing") return;
    at.value = Math.min(playing.value.length, at.value + 1);
  }, 1000);

  void read();

  onBeforeUnmount(() => {
    window.clearInterval(polling);
    window.clearInterval(ticking);
  });

  return { playing, pending, error, at, read, tell };
}

/// `2:04`. Music answers in whole seconds and nothing here is longer than an
/// hour that anybody wants to read as one.
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  return `${minutes}:${String(whole % 60).padStart(2, "0")}`;
}
