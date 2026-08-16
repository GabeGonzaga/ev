// How loud it is right now, 0..1.
//
// One number, read by the orb and by nothing else that matters. It comes from
// two different places at two different moments -- the microphone while E.V.
// is being spoken to, the speech it is playing back while it answers -- and
// the orb must not know which. So this switches sources underneath and keeps
// returning the same number.
//
// With no source at all it makes one up, because an orb that is dead flat
// until a microphone is granted is an orb nobody can develop against.

import { onBeforeUnmount, ref, type Ref } from "vue";
import { useFrame } from "./useFrame";

export type LevelSource =
  | { kind: "mic"; stream: MediaStream }
  | { kind: "playback"; element: HTMLMediaElement }
  | { kind: "none" };

export interface AudioLevel {
  /// 0..1, raw. Smoothing belongs to whatever is drawing: a meter and an orb
  /// want different amounts of it.
  level: Ref<number>;
  listen: (source: LevelSource) => void;
  stop: () => void;
}

/// Small enough to answer within a frame, big enough that the RMS of one read
/// is not one syllable's worth of luck.
const FFT = 512;

/// Speech at a normal distance from a laptop microphone lands around 0.1 RMS.
/// This is the gain that puts that in the top half of the orb's range rather
/// than the bottom tenth.
const GAIN = 4.5;

export function useAudioLevel(): AudioLevel {
  const level = ref(0);

  let context: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let source: AudioNode | null = null;
  let samples: Uint8Array<ArrayBuffer> | null = null;

  // An element can only ever be given one MediaElementSourceNode, and asking
  // twice throws. Kept here so switching back to a player that has been used
  // before reuses its node.
  const players = new WeakMap<HTMLMediaElement, MediaElementAudioSourceNode>();

  function wake(): AnalyserNode {
    if (!context) context = new AudioContext();
    if (!analyser) {
      analyser = context.createAnalyser();
      analyser.fftSize = FFT;
      samples = new Uint8Array(new ArrayBuffer(analyser.fftSize));
    }
    return analyser;
  }

  function listen(next: LevelSource) {
    source?.disconnect();
    source = null;

    if (next.kind === "none") return;

    const node = wake();
    if (next.kind === "mic") {
      // Never connected to the destination: a microphone routed to the
      // speakers is a feedback loop with a user in it.
      source = context!.createMediaStreamSource(next.stream);
      source.connect(node);
      return;
    }

    const existing = players.get(next.element);
    const player = existing ?? context!.createMediaElementSource(next.element);
    players.set(next.element, player);
    source = player;
    player.connect(node);
    // Routed onward, or taking the level would silence the answer.
    node.connect(context!.destination);
  }

  function stop() {
    source?.disconnect();
    source = null;
    level.value = 0;
  }

  useFrame((now) => {
    if (analyser && samples && source) {
      analyser.getByteTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) {
        // Bytes centred on 128; what is wanted is the swing either side.
        const swing = (samples[i] - 128) / 128;
        sum += swing * swing;
      }
      const rms = Math.sqrt(sum / samples.length);
      level.value = Math.min(1, rms * GAIN);
      return;
    }

    // Nothing attached: something that moves like speech rather than a sine,
    // which is flat and obviously fake at exactly the moment the orb is being
    // judged. Three periods beating against each other, floored at silence.
    const t = now / 1000;
    const shape =
      Math.sin(t * 2.1) * 0.5 + Math.sin(t * 5.3) * 0.3 + Math.sin(t * 11.7) * 0.2;
    level.value = Math.max(0, shape) * 0.7;
  });

  onBeforeUnmount(() => {
    stop();
    void context?.close();
    context = null;
    analyser = null;
  });

  return { level, listen, stop };
}
