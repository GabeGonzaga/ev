export type Event =
  | (TranscriptionPartial | SpeechRequested | ConfirmationRequired | ToolCompleted | StateChanged | PermissionChanged)
  | null;
export type Text = string;
export type Type = "transcription.partial";
export type Interrupt = boolean;
export type Text1 = string;
export type Type1 = "speech.requested";
/**
 * A locale, e.g. pt-PT.
 */
export type Voice = string;
/**
 * Echoed back in confirmation.respond.
 */
export type Id = string;
/**
 * Declared per tool in `tools.py`, never inferred from the arguments.
 */
export type RiskLevel = "safe" | "sensitive" | "destructive";
export type Tool = string;
export type Type2 = "confirmation.required";
export type Error = string | null;
export type Ok = boolean;
export type Speech = string | null;
export type Tool1 = string;
export type Type3 = "tool.completed";
export type State = "idle" | "listening" | "thinking" | "acting" | "speaking";
export type Type4 = "state.changed";
/**
 * A capability macOS gates behind TCC.
 */
export type Permission = "microphone" | "camera" | "accessibility" | "apple_events";
/**
 * What the host last reported for a permission.
 */
export type PermissionState = "granted" | "denied" | "undetermined";
export type Type5 = "permission.changed";
export type ErrorCode = string | null;
export type ErrorMessage = string | null;
export type Id1 = number;
export type Ok1 = boolean;
/**
 * ISO 8601, UTC, stamped when it happened.
 */
export type RecordedAt = string;
export type Speech1 = string | null;
export type Tool2 = string;
export type Entries = JournalEntry[];
export type Command = Hello | UtteranceSubmit | AudioSubmit | ConfirmationRespond | HistoryQuery | SessionCancel;
/**
 * Who is connecting, for the log.
 */
export type Client = string;
/**
 * The protocol version the client speaks.
 */
export type Protocol = string;
export type Type6 = "hello";
/**
 * The session locale, e.g. pt-PT. Carried, never used to translate the utterance before routing.
 */
export type Locale = string | null;
export type Text2 = string;
export type Type7 = "utterance.submit";
/**
 * base64 of a mono 16-bit PCM WAV.
 */
export type Audio = string;
/**
 * The language to transcribe as. Never 'auto': auto-detect is unreliable on short utterances, and a misdetected language becomes a tool argument.
 */
export type Locale1 = string | null;
export type SampleRate = number;
export type Type8 = "audio.submit";
export type Granted = boolean;
/**
 * The id of the confirmation.required event.
 */
export type Request1 = string;
export type Type9 = "confirmation.respond";
/**
 * Only entries older than this id. For paging.
 */
export type Before = number | null;
export type Limit = number;
/**
 * Search the trail instead of paging it: a tool, an album, a note's title. Accents are folded. Ignores `before`, because a search is not a page.
 */
export type Query = string | null;
export type Type10 = "history.query";
export type Type11 = "session.cancel";
export type Id2 = string;
export type Code = string;
export type Message = string;
export type Id3 = string;
export type Ok2 = boolean;

/**
 * Everything that crosses the socket, for the generated schema's benefit.
 *
 * Each line on the wire is one of these, so a generator emits one type per
 * language rather than three unrelated roots.
 */
export interface Envelope {
  event?: Event;
  page?: HistoryPage | null;
  request?: Request | null;
  response?: Response | null;
}
export interface TranscriptionPartial {
  text: Text;
  type?: Type;
}
/**
 * Intent, not audio. The native layer owns the device.
 */
export interface SpeechRequested {
  interrupt?: Interrupt;
  text: Text1;
  type?: Type1;
  voice: Voice;
}
export interface ConfirmationRequired {
  arguments?: Arguments;
  id: Id;
  risk: RiskLevel;
  tool: Tool;
  type?: Type2;
}
export interface Arguments {
  [k: string]: unknown;
}
export interface ToolCompleted {
  error?: Error;
  ok: Ok;
  speech?: Speech;
  tool: Tool1;
  type?: Type3;
}
export interface StateChanged {
  state: State;
  type?: Type4;
}
/**
 * The native host reporting what macOS says. The Python core never infers
 * this (invariant 7); it only ever learns it here.
 */
export interface PermissionChanged {
  permission: Permission;
  state: PermissionState;
  type?: Type5;
}
/**
 * What a `history.query` answers with, inside the response payload.
 */
export interface HistoryPage {
  entries?: Entries;
}
/**
 * What E.V. did, once.
 */
export interface JournalEntry {
  arguments?: Arguments1;
  error_code?: ErrorCode;
  error_message?: ErrorMessage;
  id: Id1;
  ok: Ok1;
  recorded_at: RecordedAt;
  risk: RiskLevel;
  speech?: Speech1;
  tool: Tool2;
}
export interface Arguments1 {
  [k: string]: unknown;
}
/**
 * A command with an id. Exactly one `Response` carries the same id back.
 */
export interface Request {
  command: Command;
  id: Id2;
}
/**
 * First message on every connection. Nothing else is served until it is
 * accepted.
 */
export interface Hello {
  client: Client;
  protocol: Protocol;
  type?: Type6;
}
export interface UtteranceSubmit {
  locale?: Locale;
  text: Text2;
  type?: Type7;
}
/**
 * Recorded speech, on its way to be transcribed.
 *
 * The host captures, because the microphone is a TCC surface and TCC grants
 * attach to a code signature. The core transcribes, because that is where
 * `SpeechRecognizer` lives and where the engine stays replaceable (ADR 0018).
 *
 * Base64 rather than a file path: a path means the audio is written to disk
 * by one process and read by another, and neither owns deleting it. ~2.5
 * seconds of 16 kHz mono is about 100 KB encoded, which is nothing on a local
 * socket.
 */
export interface AudioSubmit {
  audio: Audio;
  locale?: Locale1;
  sample_rate?: SampleRate;
  type?: Type8;
}
export interface ConfirmationRespond {
  granted: Granted;
  request: Request1;
  type?: Type9;
}
/**
 * What E.V. has done, newest first.
 *
 * A request rather than an event: history is asked for, not pushed. The
 * answer arrives in the response payload as `entries`, shaped like
 * `JournalEntry` below.
 */
export interface HistoryQuery {
  before?: Before;
  limit?: Limit;
  query?: Query;
  type?: Type10;
}
export interface SessionCancel {
  type?: Type11;
}
export interface Response {
  error?: ResponseError | null;
  id: Id3;
  ok: Ok2;
  payload?: Payload;
}
export interface ResponseError {
  code: Code;
  message: Message;
}
export interface Payload {
  [k: string]: unknown;
}
