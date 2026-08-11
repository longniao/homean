export type InterruptedSession = { fileUri: string; segmentOffsetMs: number };

export interface RecoveryStore {
  recordingSession(showingId: string): Promise<InterruptedSession | null>;
  /** Enqueue and clear the session in one durable database transaction. */
  recoverInterruptedAudio(showingId: string, session: InterruptedSession): Promise<void>;
}

/**
 * Recover the persisted segment through the repository's atomic operation.
 * Keeping the file check and recovery orchestration outside the screen makes
 * it testable; the repository owns the SQLite transaction and idempotency key.
 */
export async function recoverInterruptedSegment(
  store: RecoveryStore,
  showingId: string,
  fileExists: (fileUri: string) => boolean,
): Promise<void> {
  const session = await store.recordingSession(showingId);
  if (!session) return;
  if (!fileExists(session.fileUri)) {
    throw new Error('The recovered audio segment is no longer available on this device.');
  }

  await store.recoverInterruptedAudio(showingId, session);
}
