import { SyncEngine, syncStateFromProcessing, type SyncStore, type SyncTransport } from '../engine';
import type { LocalMedia, LocalShowing } from '../../types';

const showing = (patch: Partial<LocalShowing> = {}): LocalShowing => ({
  id: 'local-1', remoteId: null, contactId: null, subjectId: 'subject-1', address: null, title: '123 Main',
  startedAt: 1, endedAt: 2, elapsedMs: 10_000, syncState: 'local', processingStatus: null,
  finishRequested: true, lastError: null, updatedAt: 1, ...patch,
});
const media = (id: string, createdAt: number, patch: Partial<LocalMedia> = {}): LocalMedia => ({
  id, showingId: 'local-1', remoteMediaId: null, kind: 'audio', fileUri: `file:///${id}.m4a`,
  contentType: 'audio/mp4', timestampOffsetMs: 0, state: 'queued', attemptCount: 0, nextAttemptAt: 0,
  uploadUrl: null, uploadHeaders: {}, createdAt, ...patch,
});

class MemoryStore implements SyncStore {
  constructor(public showings: LocalShowing[], public media: LocalMedia[]) {}
  async pendingShowings() { return this.showings.filter((item) => ['local', 'syncing', 'failed'].includes(item.syncState)); }
  async mediaForShowing() { return this.media; }
  async patchShowing(id: string, patch: Partial<LocalShowing>) { Object.assign(this.showings.find((item) => item.id === id)!, patch); }
  async patchMedia(id: string, patch: Partial<LocalMedia>) { Object.assign(this.media.find((item) => item.id === id)!, patch); }
}
function transport(calls: string[], uploadImpl?: () => Promise<void>): SyncTransport {
  return {
    async createShowing() { calls.push('create'); return { id: 'remote-1' }; },
    async presignMedia(_visit, item) { calls.push(`presign:${item.timestampOffsetMs}`); return { media_id: `remote-media-${item.timestampOffsetMs}`, upload_url: `https://upload/${item.timestampOffsetMs}`, headers: {} }; },
    async uploadFile(url) { calls.push(`put:${url.split('/').pop()}`); await uploadImpl?.(); },
    async completeMedia(_visit, id) { calls.push(`complete:${id.split('-').pop()}`); },
    async finishShowing() { calls.push('finish'); },
  };
}

describe('SyncEngine', () => {
  test('maps real backend processing states to mobile sync states', () => {
    expect(syncStateFromProcessing('ready', 'processing')).toBe('ready');
    expect(syncStateFromProcessing('failed', 'processing')).toBe('failed');
    expect(syncStateFromProcessing('generating', 'synced')).toBe('processing');
    expect(syncStateFromProcessing('not_started', 'synced')).toBe('synced');
  });

  test('does nothing while offline and leaves the durable queue intact', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); const calls: string[] = [];
    await new SyncEngine(store, transport(calls), { isOnline: async () => false }).run();
    expect(calls).toEqual([]); expect(store.media[0]!.state).toBe('queued');
  });

  test('uploads in capture order and finishes only after every completion', async () => {
    const first = media('audio', 1, { timestampOffsetMs: 0 }); const second = media('photo', 2, { kind: 'photo', contentType: 'image/jpeg', timestampOffsetMs: 5000 });
    const store = new MemoryStore([showing()], [second, first]); const calls: string[] = [];
    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();
    expect(calls).toEqual(['create', 'presign:0', 'put:0', 'complete:0', 'presign:5000', 'put:5000', 'complete:5000', 'finish']);
    expect(store.showings[0]!.syncState).toBe('processing');
    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();
    expect(calls.filter((call) => call === 'finish')).toHaveLength(1);
  });

  test('syncs a property-free showing through create, upload, and finish', async () => {
    const propertyFree = showing({ subjectId: null, address: null });
    const store = new MemoryStore([propertyFree], [media('audio', 1)]); const calls: string[] = [];
    const syncTransport = transport(calls); const inputs: { subjectId: string | null; address: string | null; contactId: string | null }[] = [];
    const createShowing = syncTransport.createShowing;
    syncTransport.createShowing = async (input) => { inputs.push(input); return createShowing(input); };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true }).run();

    expect(inputs).toEqual([{ subjectId: null, address: null, contactId: null }]);
    expect(calls).toEqual(['create', 'presign:0', 'put:0', 'complete:0', 'finish']);
    expect(propertyFree).toMatchObject({ remoteId: 'remote-1', syncState: 'processing' });
  });

  test('records exponential retry state after a failed upload', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); let now = 10_000;
    const engine = new SyncEngine(store, transport([], async () => { throw new Error('offline'); }), { isOnline: async () => true, now: () => now, baseRetryMs: 1000 });
    await engine.run(); expect(store.media[0]).toMatchObject({ state: 'failed', attemptCount: 1, nextAttemptAt: 11_000 });
    now = 11_000; await engine.run(); expect(store.media[0]).toMatchObject({ attemptCount: 2, nextAttemptAt: 13_000 });
  });

  test('resumes a persisted partial upload without creating a duplicate media row', async () => {
    const existing = media('audio', 1, { remoteMediaId: 'remote-media-0', uploadUrl: 'https://upload/0', state: 'uploading' });
    const store = new MemoryStore([showing({ remoteId: 'remote-1' })], [existing]); const calls: string[] = [];
    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();
    expect(calls).toEqual(['put:0', 'complete:0', 'finish']); expect(store.media).toHaveLength(1); expect(existing.state).toBe('completed');
  });
});
