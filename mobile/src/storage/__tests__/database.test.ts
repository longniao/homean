import * as SQLite from 'expo-sqlite';
import { CaptureRepository } from '../database';

jest.mock('expo-sqlite', () => ({ openDatabaseAsync: jest.fn() }));

type Session = { file_uri: string; segment_offset_ms: number };
type Media = {
  id: string; showing_id: string; remote_media_id: string | null; kind: 'audio'; file_uri: string;
  content_type: string; timestamp_offset_ms: number; state: 'queued'; attempt_count: number;
  next_attempt_at: number; upload_url: string | null; upload_headers: string;
  upload_expires_at: number | null; recovery_key: string | null; created_at: number;
};
type Marker = {
  id: string; showing_id: string; remote_marker_id: string | null; marker_type: 'voice_tag';
  timestamp_offset_ms: number; state: 'queued'; attempt_count: number; next_attempt_at: number;
  last_error: string | null; created_at: number;
};
type Showing = { id: string; sync_state: string; updated_at: number; generation: number };

class FakeDatabase {
  session: Session | null = null;
  media: Media[] = [];
  markers: Marker[] = [];
  showing: Showing = { id: 'showing-1', sync_state: 'synced', updated_at: 1, generation: 0 };
  failBeforeCommit = false;
  failNormalInsert: 'media' | 'marker' | null = null;
  onShowingUpdate: (() => Promise<void>) | null = null;
  private parent: FakeDatabase | null = null;

  async execAsync(_sql: string): Promise<void> {}

  async getFirstAsync<T>(sql: string, ...params: unknown[]): Promise<T | null> {
    if (sql.includes('FROM recording_sessions')) return this.session as T | null;
    if (sql.includes('FROM local_media WHERE recovery_key')) {
      return (this.media.find((item) => item.recovery_key === params[0]) ?? null) as T | null;
    }
    if (sql.includes('FROM local_media WHERE showing_id')) {
      const [showingId, kind, fileUri, timestampOffsetMs] = params;
      return (this.media.find((item) => item.showing_id === showingId && item.kind === kind && item.file_uri === fileUri && item.timestamp_offset_ms === timestampOffsetMs && item.recovery_key === null) ?? null) as T | null;
    }
    if (sql.includes('FROM local_media WHERE id')) {
      return (this.media.find((item) => item.id === params[0]) ?? null) as T | null;
    }
    if (sql.includes('FROM voice_tags WHERE id')) {
      return (this.markers.find((item) => item.id === params[0]) ?? null) as T | null;
    }
    if (sql.includes('FROM local_showings WHERE id')) return (this.showing.id === params[0] ? this.showing : null) as T | null;
    return null;
  }

  async getAllAsync<T>(sql: string, ...params: unknown[]): Promise<T[]> {
    if (sql.includes('FROM local_showings WHERE sync_state IN')) {
      return (['local', 'syncing', 'failed'].includes(this.showing.sync_state) ? [this.showing] : []) as T[];
    }
    if (sql.includes('FROM local_media WHERE showing_id')) {
      return this.media.filter((item) => item.showing_id === params[0]) as T[];
    }
    if (sql.includes('FROM voice_tags WHERE showing_id')) {
      return this.markers.filter((item) => item.showing_id === params[0]) as T[];
    }
    return [];
  }

  async runAsync(sql: string, ...params: unknown[]): Promise<{ changes: number; lastInsertRowId: number }> {
    if (sql.startsWith('UPDATE local_media SET recovery_key')) {
      const [recoveryKey, id] = params as [string, string];
      const item = this.media.find((candidate) => candidate.id === id);
      if (item) item.recovery_key = recoveryKey;
      return { changes: item ? 1 : 0, lastInsertRowId: 0 };
    }
    if (sql.startsWith('INSERT INTO local_media')) {
      const controller = this.parent ?? this;
      if (sql.includes('recovery_key')) {
        const [id, showingId, fileUri, timestampOffsetMs, recoveryKey, createdAt] = params as [string, string, string, number, string, number];
        this.media.push({
          id, showing_id: showingId, remote_media_id: null, kind: 'audio', file_uri: fileUri,
          content_type: 'audio/mp4', timestamp_offset_ms: timestampOffsetMs, state: 'queued',
          attempt_count: 0, next_attempt_at: 0, upload_url: null, upload_headers: '{}',
          upload_expires_at: null, recovery_key: recoveryKey, created_at: createdAt,
        });
      } else {
        if (controller.failNormalInsert === 'media') {
          controller.failNormalInsert = null;
          throw new Error('simulated media enqueue failure');
        }
        const [id, showingId, kind, fileUri, contentType, timestampOffsetMs, createdAt] = params as [string, string, 'audio', string, string, number, number];
        this.media.push({
          id, showing_id: showingId, remote_media_id: null, kind, file_uri: fileUri,
          content_type: contentType, timestamp_offset_ms: timestampOffsetMs, state: 'queued',
          attempt_count: 0, next_attempt_at: 0, upload_url: null, upload_headers: '{}',
          upload_expires_at: null, recovery_key: null, created_at: createdAt,
        });
      }
      return { changes: 1, lastInsertRowId: 0 };
    }
    if (sql.startsWith('INSERT INTO voice_tags')) {
      const controller = this.parent ?? this;
      if (controller.failNormalInsert === 'marker') {
        controller.failNormalInsert = null;
        throw new Error('simulated marker enqueue failure');
      }
      const [id, showingId, timestampOffsetMs, createdAt] = params as [string, string, number, number];
      this.markers.push({
        id, showing_id: showingId, remote_marker_id: null, marker_type: 'voice_tag', timestamp_offset_ms: timestampOffsetMs,
        state: 'queued', attempt_count: 0, next_attempt_at: 0, last_error: null, created_at: createdAt,
      });
      return { changes: 1, lastInsertRowId: 0 };
    }
    if (sql.includes("sync_state = 'local'")) {
      const [updatedAt, showingId] = params as [number, string];
      if (this.showing.id !== showingId) return { changes: 0, lastInsertRowId: 0 };
      this.showing = { ...this.showing, sync_state: 'local', updated_at: updatedAt, generation: this.showing.generation + 1 };
      const hook = this.parent?.onShowingUpdate ?? this.onShowingUpdate;
      if (hook) await hook();
      return { changes: 1, lastInsertRowId: 0 };
    }
    if (sql.startsWith('UPDATE local_showings SET')) {
      const [syncState, showingId, expectedGeneration] = params as [string, string, number];
      if (this.showing.id !== showingId || this.showing.generation !== expectedGeneration) return { changes: 0, lastInsertRowId: 0 };
      this.showing = { ...this.showing, sync_state: syncState, generation: this.showing.generation + 1 };
      return { changes: 1, lastInsertRowId: 0 };
    }
    if (sql.startsWith('DELETE FROM recording_sessions')) {
      const controller = this.parent ?? this;
      if (this.failBeforeCommit) {
        this.failBeforeCommit = false;
        controller.failBeforeCommit = false;
        throw new Error('simulated crash before commit');
      }
      this.session = null;
      return { changes: 1, lastInsertRowId: 0 };
    }
    return { changes: 0, lastInsertRowId: 0 };
  }

  async withExclusiveTransactionAsync(task: (transaction: FakeDatabase) => Promise<void>): Promise<void> {
    const transaction = this.transactionCopy();
    try {
      await task(transaction);
      this.session = transaction.session;
      this.media = transaction.media;
      this.markers = transaction.markers;
      this.showing = transaction.showing;
    } catch (error) {
      throw error;
    }
  }

  private transactionCopy(): FakeDatabase {
    const transaction = new FakeDatabase();
    transaction.session = this.session ? { ...this.session } : null;
    transaction.media = this.media.map((item) => ({ ...item }));
    transaction.markers = this.markers.map((item) => ({ ...item }));
    transaction.showing = { ...this.showing };
    transaction.failBeforeCommit = this.failBeforeCommit;
    transaction.failNormalInsert = this.failNormalInsert;
    transaction.parent = this;
    return transaction;
  }
}

const sqlite = SQLite as unknown as { openDatabaseAsync: jest.Mock };
const db = new FakeDatabase();
const repository = new CaptureRepository();

beforeAll(() => {
  sqlite.openDatabaseAsync.mockResolvedValue(db);
});

beforeEach(() => {
  db.session = { file_uri: 'file:///prior.m4a', segment_offset_ms: 12_000 };
  db.media = [];
  db.markers = [];
  db.showing = { id: 'showing-1', sync_state: 'synced', updated_at: 1, generation: 0 };
  db.failBeforeCommit = false;
  db.failNormalInsert = null;
  db.onShowingUpdate = null;
});

describe('CaptureRepository atomic normal enqueue', () => {
  test.each([
    ['media', async () => repository.enqueueMedia({ showingId: 'showing-1', kind: 'audio', fileUri: 'file:///capture.m4a', contentType: 'audio/mp4', timestampOffsetMs: 2_000 })],
    ['voice tag', async () => repository.addVoiceTag('showing-1', 2_000)],
  ])('does not expose a syncable showing without its %s', async (_childType, enqueue) => {
    const observations: { pendingShowings: number; media: number; markers: number }[] = [];
    db.onShowingUpdate = async () => {
      db.onShowingUpdate = null;
      observations.push({
        pendingShowings: (await repository.pendingShowings()).length,
        media: (await repository.mediaForShowing('showing-1')).length,
        markers: (await repository.markersForShowing('showing-1')).length,
      });
    };

    await enqueue();

    expect(observations).toEqual([{ pendingShowings: 0, media: 0, markers: 0 }]);
    expect(db.showing).toMatchObject({ sync_state: 'local', generation: 1 });
    expect(db.media.length + db.markers.length).toBe(1);
    expect((await repository.pendingShowings()).length).toBe(1);
  });

  test.each([
    ['media', async () => repository.enqueueMedia({ showingId: 'showing-1', kind: 'audio', fileUri: 'file:///capture.m4a', contentType: 'audio/mp4', timestampOffsetMs: 2_000 })],
    ['voice tag', async () => repository.addVoiceTag('showing-1', 2_000)],
  ])('keeps a stale sync CAS from overwriting the %s enqueue', async (_childType, enqueue) => {
    const staleGeneration = db.showing.generation;

    await enqueue();

    await expect(repository.patchShowing('showing-1', { syncState: 'syncing' }, staleGeneration)).resolves.toBe(false);
    expect(db.showing).toMatchObject({ sync_state: 'local', generation: staleGeneration + 1 });
  });

  test.each([
    ['media', async () => repository.enqueueMedia({ showingId: 'showing-1', kind: 'audio', fileUri: 'file:///capture.m4a', contentType: 'audio/mp4', timestampOffsetMs: 2_000 })],
    ['voice tag', async () => repository.addVoiceTag('showing-1', 2_000)],
  ])('rolls back the showing generation/state when %s insertion fails', async (childType, enqueue) => {
    db.failNormalInsert = childType === 'media' ? 'media' : 'marker';

    await expect(enqueue()).rejects.toThrow(`simulated ${childType === 'media' ? 'media' : 'marker'} enqueue failure`);
    expect(db.showing).toMatchObject({ sync_state: 'synced', updated_at: 1, generation: 0 });
    expect(db.media).toHaveLength(0);
    expect(db.markers).toHaveLength(0);

    await enqueue();
    expect(db.showing).toMatchObject({ sync_state: 'local', generation: 1 });
    expect(db.media.length + db.markers.length).toBe(1);
  });
});

describe('CaptureRepository interrupted audio recovery', () => {
  test('rolls back the queue row with the session and replays it exactly once', async () => {
    db.failBeforeCommit = true;

    await expect(repository.recoverInterruptedAudio('showing-1', { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 })).rejects.toThrow('before commit');
    expect(db.session).not.toBeNull();
    expect(db.media).toHaveLength(0);

    await repository.recoverInterruptedAudio('showing-1', { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 });
    await repository.recoverInterruptedAudio('showing-1', { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 });

    expect(db.session).toBeNull();
    expect(db.media).toHaveLength(1);
    expect(db.showing.sync_state).toBe('local');
  });

  test('adopts a legacy queued row instead of inserting a duplicate', async () => {
    db.media = [{
      id: 'legacy-media', showing_id: 'showing-1', remote_media_id: null, kind: 'audio', file_uri: 'file:///prior.m4a',
      content_type: 'audio/mp4', timestamp_offset_ms: 12_000, state: 'queued', attempt_count: 0,
      next_attempt_at: 0, upload_url: null, upload_headers: '{}', upload_expires_at: null,
      recovery_key: null, created_at: 2,
    }];

    await repository.recoverInterruptedAudio('showing-1', { fileUri: 'file:///prior.m4a', segmentOffsetMs: 12_000 });

    expect(db.session).toBeNull();
    expect(db.media).toHaveLength(1);
    expect(db.media[0]!.recovery_key).toContain('showing-1');
  });
});
