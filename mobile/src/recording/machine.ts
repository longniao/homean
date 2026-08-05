export type RecordingPhase = 'idle' | 'preparing' | 'recording' | 'interrupted' | 'stopping' | 'stopped' | 'error';
export interface RecordingState { phase: RecordingPhase; elapsedMs: number; segmentStartedAtMs: number; error: string | null }
export type RecordingEvent =
  | { type: 'START' } | { type: 'READY'; at: number } | { type: 'TICK'; elapsedMs: number }
  | { type: 'INTERRUPTED'; error?: string } | { type: 'RESUME' } | { type: 'STOP' }
  | { type: 'STOPPED' } | { type: 'FAIL'; error: string } | { type: 'RESTORE'; elapsedMs: number };

export const initialRecordingState: RecordingState = { phase: 'idle', elapsedMs: 0, segmentStartedAtMs: 0, error: null };

export function recordingReducer(state: RecordingState, event: RecordingEvent): RecordingState {
  switch (event.type) {
    case 'START': case 'RESUME': return { ...state, phase: 'preparing', error: null };
    case 'READY': return { ...state, phase: 'recording', segmentStartedAtMs: event.at, error: null };
    case 'TICK': return state.phase === 'recording' ? { ...state, elapsedMs: Math.max(state.elapsedMs, event.elapsedMs) } : state;
    case 'INTERRUPTED': return { ...state, phase: 'interrupted', error: event.error ?? null };
    case 'STOP': return { ...state, phase: 'stopping' };
    case 'STOPPED': return { ...state, phase: 'stopped' };
    case 'FAIL': return { ...state, phase: 'error', error: event.error };
    case 'RESTORE': return { phase: 'interrupted', elapsedMs: event.elapsedMs, segmentStartedAtMs: event.elapsedMs, error: null };
    default: return state;
  }
}

export function formatElapsed(elapsedMs: number): string {
  const seconds = Math.floor(elapsedMs / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}
