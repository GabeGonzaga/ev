// The lens, and the one stream both views share.
//
// One camera, opened once. The background and the small window are two ways
// of looking at the same MediaStream -- switching between them must not stop
// and restart the device, because that is a second permission prompt on some
// machines and a visible stutter on all of them.
//
// Invariant 8, in the three places it bites: the display says so for exactly
// as long as the lens is open, the session has an end, and nothing is kept.
// There is no recording here and no frame is written anywhere.

import { onBeforeUnmount, ref, type Ref } from "vue";

export interface Lens {
  stream: Ref<MediaStream | null>;
  live: Ref<boolean>;
  error: Ref<string | null>;
  /// Seconds left of the session, counted down where it can be seen.
  left: Ref<number>;
  open: () => Promise<void>;
  close: () => void;
}

/// Long enough to look at something, short enough that a window left open is
/// not a camera left on.
export const SESSION = 180;

export function useCamera(): Lens {
  const stream = ref<MediaStream | null>(null);
  const live = ref(false);
  const error = ref<string | null>(null);
  const left = ref(0);
  let ticking = 0;

  async function open() {
    if (stream.value) return;
    error.value = null;

    try {
      // In a browser this asks in the browser's name. In the app it asks in
      // E.V.'s: the webview is part of the signed process, so the permission
      // macOS grants is the signed host's, which is what invariant 7 is
      // about -- not which window happens to draw the picture.
      stream.value = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      live.value = true;
      left.value = SESSION;
      ticking = window.setInterval(() => {
        left.value -= 1;
        if (left.value <= 0) close();
      }, 1000);
    } catch (refused) {
      // A refusal is an answer, and it is the user's. Reported, not retried.
      error.value = String(refused instanceof Error ? refused.message : refused);
      live.value = false;
    }
  }

  function close() {
    window.clearInterval(ticking);
    stream.value?.getTracks().forEach((track) => track.stop());
    stream.value = null;
    live.value = false;
    left.value = 0;
  }

  onBeforeUnmount(close);

  return { stream, live, error, left, open, close };
}

/// One still, for a question about what is on screen. Made, handed over, and
/// dropped -- it is never held and never written anywhere.
export function still(video: HTMLVideoElement): string | null {
  if (!video.videoWidth) return null;
  const frame = document.createElement("canvas");
  frame.width = video.videoWidth;
  frame.height = video.videoHeight;
  frame.getContext("2d")?.drawImage(video, 0, 0);
  return frame.toDataURL("image/jpeg", 0.82);
}
