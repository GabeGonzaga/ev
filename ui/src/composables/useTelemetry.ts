// The numbers along the bottom edge.
//
// Deliberately boring: uptime, the model, a round-trip in milliseconds, which
// microphone, and whether the core is answering. Nobody reads a telemetry
// strip -- they glance at it to see that it is still moving, and they read it
// only on the day something is wrong. So it is dense, small, dim, and honest.
//
// Stubbed, like everything else in this UI. The shapes are what the core
// already reports; the values are invented.

import { onBeforeUnmount, ref } from "vue";
import { stub, type Source } from "./source";

export interface Telemetry {
  /// Seconds since the core came up.
  uptime: number;
  model: string;
  /// Last turn's round trip, milliseconds.
  latency: number;
  mic: string;
  connection: "linked" | "degraded" | "offline";
}

export function useTelemetry(): Source<Telemetry> {
  const source = stub<Telemetry>(
    () => ({
      uptime: 4271,
      model: "qwen3:8b",
      latency: 1310,
      mic: "MacBook Pro Microphone",
      connection: "linked",
    }),
    { latency: 300 },
  );

  // Moving, because a strip of numbers that never changes reads as a picture
  // of a strip of numbers. One timer, one second: this is the cheapest thing
  // on the screen and it should stay that way.
  const timer = ref(
    window.setInterval(() => {
      const now = source.data.value;
      if (!now) return;
      now.uptime += 1;
      // Latency wanders around what the router actually measures rather than
      // walking off in one direction.
      now.latency = Math.round(1310 + Math.sin(now.uptime / 7) * 120);
    }, 1000),
  );

  onBeforeUnmount(() => window.clearInterval(timer.value));
  return source;
}

/// Seconds as `04:271` reads as nothing. Hours and minutes read as uptime.
export function asUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(rest)}`;
}
