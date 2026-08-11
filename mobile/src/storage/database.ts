import * as Crypto from 'expo-crypto';
import * as SQLite from 'expo-sqlite';
import type { LocalMarker, LocalMedia, LocalShowing, MediaKind, SyncState } from '../types';
import type { SyncStore } from '../sync/engine';

let databasePromise: Promise<SQLite.SQLiteDatabase> | null = null;

async function database(): Promise<SQLite.SQLiteDatabase> {
  databasePromise ??= SQLite.openDatabaseAsync('kawu-capture.db');
  const db = await databasePromise;
  await db.execAsync(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS local_showings (
      id TEXT PRIMARY KEY NOT NULL, remote_id TEXT, contact_id TEXT, subject_id TEXT, address TEXT,
      title TEXT NOT NULL, started_at INTEGER NOT NULL, ended_at INTEGER, elapsed_ms INTEGER NOT NULL DEFAULT 0,
      sync_state TEXT NOT NULL, processing_status TEXT, finish_requested INTEGER NOT NULL DEFAULT 0,
      last_error TEXT, updated_at INTEGER NOT NULL, generation INTEGER NOT NULL DEFAULT 0
      , consent_ack INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS local_media (
      id TEXT PRIMARY KEY NOT NULL, showing_id TEXT NOT NULL REFERENCES local_showings(id) ON DELETE CASCADE,
      remote_media_id TEXT, kind TEXT NOT NULL, file_uri TEXT NOT NULL, content_type TEXT NOT NULL,
      timestamp_offset_ms INTEGER NOT NULL, state TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
      next_attempt_at INTEGER NOT NULL DEFAULT 0, upload_url TEXT, upload_headers TEXT NOT NULL DEFAULT '{}',
      upload_expires_at INTEGER, recovery_key TEXT, created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS voice_tags (
      id TEXT PRIMARY KEY NOT NULL, showing_id TEXT NOT NULL REFERENCES local_showings(id) ON DELETE CASCADE,
      timestamp_offset_ms INTEGER NOT NULL, created_at INTEGER NOT NULL,
      remote_marker_id TEXT, state TEXT NOT NULL DEFAULT 'queued',
      attempt_count INTEGER NOT NULL DEFAULT 0, next_attempt_at INTEGER NOT NULL DEFAULT 0,
      last_error TEXT
    );
    CREATE TABLE IF NOT EXISTS recording_sessions (
      showing_id TEXT PRIMARY KEY NOT NULL REFERENCES local_showings(id) ON DELETE CASCADE,
      file_uri TEXT NOT NULL, segment_offset_ms INTEGER NOT NULL, updated_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_local_media_showing ON local_media(showing_id, created_at);
  `);
  try { await db.execAsync('ALTER TABLE local_showings ADD COLUMN consent_ack INTEGER NOT NULL DEFAULT 0'); } catch { /* already present */ }
  try { await db.execAsync('ALTER TABLE local_showings ADD COLUMN generation INTEGER NOT NULL DEFAULT 0'); } catch { /* already present */ }
  try { await db.execAsync('ALTER TABLE local_media ADD COLUMN upload_expires_at INTEGER'); } catch { /* already present */ }
  try { await db.execAsync('ALTER TABLE local_media ADD COLUMN recovery_key TEXT'); } catch { /* already present */ }
  await db.execAsync('CREATE UNIQUE INDEX IF NOT EXISTS idx_local_media_recovery_key ON local_media(recovery_key)');
  for (const statement of [
    "ALTER TABLE voice_tags ADD COLUMN remote_marker_id TEXT",
    "ALTER TABLE voice_tags ADD COLUMN state TEXT NOT NULL DEFAULT 'queued'",
    "ALTER TABLE voice_tags ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE voice_tags ADD COLUMN next_attempt_at INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE voice_tags ADD COLUMN last_error TEXT",
  ]) {
    try { await db.execAsync(statement); } catch { /* column already exists */ }
  }
  return db;
}

type ShowingRow = {
  id: string; remote_id: string | null; contact_id: string | null; subject_id: string | null; address: string | null;
  title: string; started_at: number; ended_at: number | null; elapsed_ms: number; sync_state: SyncState;
  processing_status: string | null; finish_requested: number; last_error: string | null; updated_at: number;
  generation: number; consent_ack: number;
};
type MediaRow = {
  id: string; showing_id: string; remote_media_id: string | null; kind: MediaKind; file_uri: string;
  content_type: string; timestamp_offset_ms: number; state: LocalMedia['state']; attempt_count: number;
  next_attempt_at: number; upload_url: string | null; upload_headers: string; upload_expires_at: number | null;
  recovery_key: string | null; created_at: number;
};
type MarkerRow = {
  id: string; showing_id: string; remote_marker_id: string | null; marker_type: 'voice_tag';
  timestamp_offset_ms: number; state: LocalMarker['state']; attempt_count: number;
  next_attempt_at: number; last_error: string | null; created_at: number;
};
const toShowing = (row: ShowingRow): LocalShowing => ({
  id: row.id, remoteId: row.remote_id, contactId: row.contact_id, subjectId: row.subject_id, address: row.address,
  title: row.title, startedAt: row.started_at, endedAt: row.ended_at, elapsedMs: row.elapsed_ms,
  syncState: row.sync_state, processingStatus: row.processing_status, finishRequested: Boolean(row.finish_requested),
  lastError: row.last_error, updatedAt: row.updated_at, generation: row.generation,
  consentAck: Boolean(row.consent_ack),
});
const toMedia = (row: MediaRow): LocalMedia => ({
  id: row.id, showingId: row.showing_id, remoteMediaId: row.remote_media_id, kind: row.kind,
  fileUri: row.file_uri, contentType: row.content_type, timestampOffsetMs: row.timestamp_offset_ms,
  state: row.state, attemptCount: row.attempt_count, nextAttemptAt: row.next_attempt_at,
  uploadUrl: row.upload_url, uploadHeaders: JSON.parse(row.upload_headers) as Record<string, string>, uploadExpiresAt: row.upload_expires_at,
  recoveryKey: row.recovery_key, createdAt: row.created_at,
});
const toMarker = (row: MarkerRow): LocalMarker => ({
  id: row.id, showingId: row.showing_id, remoteMarkerId: row.remote_marker_id,
  markerType: row.marker_type, timestampOffsetMs: row.timestamp_offset_ms,
  state: row.state, attemptCount: row.attempt_count, nextAttemptAt: row.next_attempt_at,
  lastError: row.last_error, createdAt: row.created_at,
});

export class CaptureRepository implements SyncStore {
  async createShowing(input: { contactId: string | null; subjectId: string | null; address: string | null; title: string; consentAck?: boolean }): Promise<LocalShowing> {
    const now = Date.now(); const id = Crypto.randomUUID(); const db = await database();
    await db.runAsync('INSERT INTO local_showings (id, contact_id, subject_id, address, title, started_at, sync_state, updated_at, generation, consent_ack) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', id, input.contactId, input.subjectId, input.address, input.title, now, 'local', now, 0, input.consentAck ? 1 : 0);
    return (await this.getShowing(id))!;
  }
  async getShowing(id: string): Promise<LocalShowing | null> {
    const row = await (await database()).getFirstAsync<ShowingRow>('SELECT * FROM local_showings WHERE id = ?', id);
    return row ? toShowing(row) : null;
  }
  async activeShowing(): Promise<LocalShowing | null> {
    const row = await (await database()).getFirstAsync<ShowingRow>('SELECT * FROM local_showings WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1');
    return row ? toShowing(row) : null;
  }
  async listShowings(): Promise<LocalShowing[]> {
    return (await (await database()).getAllAsync<ShowingRow>('SELECT * FROM local_showings ORDER BY started_at DESC')).map(toShowing);
  }
  async pendingShowings(): Promise<LocalShowing[]> {
    return (await (await database()).getAllAsync<ShowingRow>("SELECT * FROM local_showings WHERE sync_state IN ('local', 'syncing', 'failed') ORDER BY started_at")).map(toShowing);
  }
  async patchShowing(id: string, patch: Partial<Pick<LocalShowing, 'remoteId' | 'syncState' | 'processingStatus' | 'lastError' | 'updatedAt'>>, expectedGeneration?: number): Promise<boolean> {
    const map: Record<string, string> = { remoteId: 'remote_id', syncState: 'sync_state', processingStatus: 'processing_status', lastError: 'last_error', updatedAt: 'updated_at' };
    const entries = Object.entries(patch); if (!entries.length) return true;
    const predicate = expectedGeneration === undefined ? 'id = ?' : 'id = ? AND generation = ?';
    const result = await (await database()).runAsync(`UPDATE local_showings SET ${entries.map(([key]) => `${map[key]} = ?`).join(', ')}, generation = generation + 1 WHERE ${predicate}`, ...entries.map(([, value]) => value ?? null), id, ...(expectedGeneration === undefined ? [] : [expectedGeneration]));
    return result.changes > 0;
  }
  async updateElapsed(id: string, elapsedMs: number): Promise<void> {
    await (await database()).runAsync('UPDATE local_showings SET elapsed_ms = ?, updated_at = ?, generation = generation + 1 WHERE id = ?', elapsedMs, Date.now(), id);
  }
  async finish(id: string, elapsedMs: number): Promise<void> {
    const now = Date.now();
    await (await database()).runAsync("UPDATE local_showings SET ended_at = ?, elapsed_ms = ?, finish_requested = 1, sync_state = 'local', updated_at = ?, generation = generation + 1 WHERE id = ?", now, elapsedMs, now, id);
  }
  async enqueueMedia(input: { showingId: string; kind: MediaKind; fileUri: string; contentType: string; timestampOffsetMs: number }): Promise<LocalMedia> {
    const db = await database(); const id = Crypto.randomUUID(); const now = Date.now();
    let row: MediaRow | null = null;
    await db.withExclusiveTransactionAsync(async (txn) => {
      await txn.runAsync("UPDATE local_showings SET sync_state = 'local', updated_at = ?, generation = generation + 1 WHERE id = ?", now, input.showingId);
      await txn.runAsync("INSERT INTO local_media (id, showing_id, kind, file_uri, content_type, timestamp_offset_ms, state, upload_expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, 'queued', NULL, ?)", id, input.showingId, input.kind, input.fileUri, input.contentType, input.timestampOffsetMs, now);
      row = await txn.getFirstAsync<MediaRow>('SELECT * FROM local_media WHERE id = ?', id);
    });
    if (!row) throw new Error('Queued media could not be read back');
    return toMedia(row);
  }
  async mediaForShowing(showingId: string): Promise<LocalMedia[]> {
    return (await (await database()).getAllAsync<MediaRow>('SELECT * FROM local_media WHERE showing_id = ? ORDER BY created_at', showingId)).map(toMedia);
  }
  async markersForShowing(showingId: string): Promise<LocalMarker[]> {
    return (await (await database()).getAllAsync<MarkerRow>('SELECT id, showing_id, remote_marker_id, \'voice_tag\' AS marker_type, timestamp_offset_ms, state, attempt_count, next_attempt_at, last_error, created_at FROM voice_tags WHERE showing_id = ? ORDER BY created_at', showingId)).map(toMarker);
  }
  async patchMedia(id: string, patch: Partial<Pick<LocalMedia, 'remoteMediaId' | 'state' | 'attemptCount' | 'nextAttemptAt' | 'uploadUrl' | 'uploadHeaders' | 'uploadExpiresAt'>>): Promise<void> {
    const map: Record<string, string> = { remoteMediaId: 'remote_media_id', state: 'state', attemptCount: 'attempt_count', nextAttemptAt: 'next_attempt_at', uploadUrl: 'upload_url', uploadHeaders: 'upload_headers', uploadExpiresAt: 'upload_expires_at' };
    const entries = Object.entries(patch); if (!entries.length) return;
    const values = entries.map(([key, value]) => key === 'uploadHeaders' ? JSON.stringify(value) : value ?? null) as (string | number | null)[];
    await (await database()).runAsync(`UPDATE local_media SET ${entries.map(([key]) => `${map[key]} = ?`).join(', ')} WHERE id = ?`, ...values, id);
  }
  async patchMarker(id: string, patch: Partial<Pick<LocalMarker, 'remoteMarkerId' | 'state' | 'attemptCount' | 'nextAttemptAt' | 'lastError'>>): Promise<void> {
    const map: Record<string, string> = { remoteMarkerId: 'remote_marker_id', state: 'state', attemptCount: 'attempt_count', nextAttemptAt: 'next_attempt_at', lastError: 'last_error' };
    const entries = Object.entries(patch); if (!entries.length) return;
    await (await database()).runAsync(`UPDATE voice_tags SET ${entries.map(([key]) => `${map[key]} = ?`).join(', ')} WHERE id = ?`, ...entries.map(([, value]) => value ?? null), id);
  }
  async addVoiceTag(showingId: string, timestampOffsetMs: number): Promise<LocalMarker> {
    const db = await database(); const id = Crypto.randomUUID(); const now = Date.now();
    // A showing can have reached `synced` during an active recording. Mark it
    // pending before inserting the tag so a crash cannot leave an orphaned
    // queued marker that the sync query will never revisit.
    let row: MarkerRow | null = null;
    await db.withExclusiveTransactionAsync(async (txn) => {
      await txn.runAsync("UPDATE local_showings SET sync_state = 'local', updated_at = ?, generation = generation + 1 WHERE id = ?", now, showingId);
      await txn.runAsync('INSERT INTO voice_tags (id, showing_id, timestamp_offset_ms, created_at, state) VALUES (?, ?, ?, ?, \'queued\')', id, showingId, timestampOffsetMs, now);
      row = await txn.getFirstAsync<MarkerRow>('SELECT id, showing_id, remote_marker_id, \'voice_tag\' AS marker_type, timestamp_offset_ms, state, attempt_count, next_attempt_at, last_error, created_at FROM voice_tags WHERE id = ?', id);
    });
    if (!row) throw new Error('Voice tag could not be read back');
    return toMarker(row);
  }
  async saveRecordingSession(showingId: string, fileUri: string, segmentOffsetMs: number): Promise<void> {
    await (await database()).runAsync(
      'INSERT INTO recording_sessions (showing_id, file_uri, segment_offset_ms, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(showing_id) DO UPDATE SET file_uri = excluded.file_uri, segment_offset_ms = excluded.segment_offset_ms, updated_at = excluded.updated_at',
      showingId, fileUri, segmentOffsetMs, Date.now(),
    );
  }
  async recordingSession(showingId: string): Promise<{ fileUri: string; segmentOffsetMs: number } | null> {
    const row = await (await database()).getFirstAsync<{ file_uri: string; segment_offset_ms: number }>('SELECT file_uri, segment_offset_ms FROM recording_sessions WHERE showing_id = ?', showingId);
    return row ? { fileUri: row.file_uri, segmentOffsetMs: row.segment_offset_ms } : null;
  }
  async recoverInterruptedAudio(showingId: string, expectedSession: { fileUri: string; segmentOffsetMs: number }): Promise<void> {
    const db = await database();
    const recoveryKey = recoveryIdentity(showingId, expectedSession);

    await db.withExclusiveTransactionAsync(async (txn) => {
      const session = await txn.getFirstAsync<{ file_uri: string; segment_offset_ms: number }>(
        'SELECT file_uri, segment_offset_ms FROM recording_sessions WHERE showing_id = ?',
        showingId,
      );
      if (!session) return;
      if (session.file_uri !== expectedSession.fileUri || session.segment_offset_ms !== expectedSession.segmentOffsetMs) {
        throw new Error('The recording session changed while recovery was starting.');
      }

      let media = await txn.getFirstAsync<MediaRow>('SELECT * FROM local_media WHERE recovery_key = ?', recoveryKey);
      if (!media) {
        // A database created before recovery became atomic may already contain
        // this exact queue row while its session still exists. Adopt it instead
        // of creating a second row during the compatibility migration.
        media = await txn.getFirstAsync<MediaRow>(
          'SELECT * FROM local_media WHERE showing_id = ? AND kind = ? AND file_uri = ? AND timestamp_offset_ms = ? AND recovery_key IS NULL ORDER BY created_at, id LIMIT 1',
          showingId, 'audio', expectedSession.fileUri, expectedSession.segmentOffsetMs,
        );
        if (media) {
          await txn.runAsync('UPDATE local_media SET recovery_key = ? WHERE id = ?', recoveryKey, media.id);
          media = await txn.getFirstAsync<MediaRow>('SELECT * FROM local_media WHERE id = ?', media.id);
        }
      }

      const now = Date.now();
      if (!media) {
        const id = Crypto.randomUUID();
        await txn.runAsync("INSERT INTO local_media (id, showing_id, kind, file_uri, content_type, timestamp_offset_ms, state, upload_expires_at, recovery_key, created_at) VALUES (?, ?, 'audio', ?, 'audio/mp4', ?, 'queued', NULL, ?, ?)", id, showingId, expectedSession.fileUri, expectedSession.segmentOffsetMs, recoveryKey, now);
        media = await txn.getFirstAsync<MediaRow>('SELECT * FROM local_media WHERE recovery_key = ?', recoveryKey);
      }
      if (!media) throw new Error('Recovered audio could not be queued');

      // Keep the showing eligible for the normal durable queue if a legacy row
      // was found after an older startup recovery attempt.
      await txn.runAsync("UPDATE local_showings SET sync_state = 'local', updated_at = ?, generation = generation + 1 WHERE id = ?", now, showingId);
      await txn.runAsync('DELETE FROM recording_sessions WHERE showing_id = ?', showingId);
    });
  }
  async clearRecordingSession(showingId: string): Promise<void> {
    await (await database()).runAsync('DELETE FROM recording_sessions WHERE showing_id = ?', showingId);
  }
}

function recoveryIdentity(showingId: string, session: { fileUri: string; segmentOffsetMs: number }): string {
  return `recording-session:${JSON.stringify([showingId, session.fileUri, session.segmentOffsetMs])}`;
}

export const captureRepository = new CaptureRepository();
