import { recoverInterruptedSegment, type RecoveryStore } from '../recovery';

describe('interrupted recording recovery', () => {
  test('delegates enqueue and clear to one atomic repository operation', async () => {
    const recovered = jest.fn(async () => undefined);
    const store: RecoveryStore = {
      recordingSession: async () => ({ fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 }),
      recoverInterruptedAudio: recovered,
    };

    await recoverInterruptedSegment(store, 'showing-1', () => true);

    expect(recovered).toHaveBeenCalledTimes(1);
    expect(recovered).toHaveBeenCalledWith('showing-1', { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 });
  });

  test('keeps the recovery row when the prior file cannot be recovered', async () => {
    const store: RecoveryStore = {
      recordingSession: async () => ({ fileUri: 'file:///missing.m4a', segmentOffsetMs: 0 }),
      recoverInterruptedAudio: jest.fn(async () => undefined),
    };

    await expect(recoverInterruptedSegment(store, 'showing-1', () => false)).rejects.toThrow('no longer available');
    expect(store.recoverInterruptedAudio).not.toHaveBeenCalled();
  });

  test('replays after a rolled-back transaction without enqueueing twice', async () => {
    let session: { fileUri: string; segmentOffsetMs: number } | null = { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 };
    const media: string[] = [];
    let failBeforeCommit = true;
    const recoverInterruptedAudio = jest.fn(async (_showingId: string, expectedSession: { fileUri: string; segmentOffsetMs: number }) => {
      if (!session) return;
      if (failBeforeCommit) {
        failBeforeCommit = false;
        throw new Error('simulated crash before commit');
      }
      media.push(expectedSession.fileUri);
      session = null;
    });
    const store: RecoveryStore = {
      recordingSession: async () => session,
      recoverInterruptedAudio,
    };

    await expect(recoverInterruptedSegment(store, 'showing-1', () => true)).rejects.toThrow('before commit');
    expect(session).not.toBeNull();
    expect(media).toEqual([]);

    await recoverInterruptedSegment(store, 'showing-1', () => true);
    await recoverInterruptedSegment(store, 'showing-1', () => true);

    expect(media).toEqual(['file:///prior.m4a']);
    expect(session).toBeNull();
    expect(recoverInterruptedAudio).toHaveBeenCalledTimes(2);
  });

  test('does not replay after a crash immediately after commit', async () => {
    let session: { fileUri: string; segmentOffsetMs: number } | null = { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 };
    const media: string[] = [];
    let firstAttempt = true;
    const recoverInterruptedAudio = jest.fn(async (_showingId: string, expectedSession: { fileUri: string; segmentOffsetMs: number }) => {
      if (!session) return;
      media.push(expectedSession.fileUri);
      session = null;
      if (firstAttempt) {
        firstAttempt = false;
        throw new Error('simulated crash after commit');
      }
    });
    const store: RecoveryStore = {
      recordingSession: async () => session,
      recoverInterruptedAudio,
    };

    await expect(recoverInterruptedSegment(store, 'showing-1', () => true)).rejects.toThrow('after commit');
    await recoverInterruptedSegment(store, 'showing-1', () => true);

    expect(media).toEqual(['file:///prior.m4a']);
    expect(recoverInterruptedAudio).toHaveBeenCalledTimes(1);
  });
});
