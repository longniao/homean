import { SyncEngine, syncStateFromProcessing, type SyncStore, type SyncTransport } from '../engine';
import type { LocalMarker, LocalMedia, LocalShowing } from '../../types';

const showing = (patch: Partial<LocalShowing> = {}): LocalShowing => ({
  id: 'local-1', remoteId: null, contactId: null, subjectId: 'subject-1', address: null, title: '123 Main',
  startedAt: 1, endedAt: 2, elapsedMs: 10_000, syncState: 'local', processingStatus: null,
  finishRequested: true, lastError: null, updatedAt: 1, generation: 0, rejectedMediaCount: 0, ...patch,
});
const media = (id: string, createdAt: number, patch: Partial<LocalMedia> = {}): LocalMedia => ({
  id, showingId: 'local-1', remoteMediaId: null, kind: 'audio', fileUri: `file:///${id}.m4a`,
  contentType: 'audio/mp4', timestampOffsetMs: 0, state: 'queued', attemptCount: 0, nextAttemptAt: 0,
  uploadUrl: null, uploadHeaders: {}, uploadExpiresAt: null, createdAt, ...patch,
});
const marker = (id: string, createdAt: number, patch: Partial<LocalMarker> = {}): LocalMarker => ({
  id, showingId: 'local-1', remoteMarkerId: null, markerType: 'voice_tag', timestampOffsetMs: 2_000,
  state: 'queued', attemptCount: 0, nextAttemptAt: 0, lastError: null, createdAt, ...patch,
});

class MemoryStore implements SyncStore {
  constructor(public showings: LocalShowing[], public media: LocalMedia[], public markers: LocalMarker[] = []) {}
  async getShowing(id: string) { return this.showings.find((item) => item.id === id) ?? null; }
  async pendingShowings() { return this.showings.filter((item) => ['local', 'syncing', 'failed'].includes(item.syncState)); }
  async mediaForShowing() { return this.media; }
  async markersForShowing() { return this.markers; }
  async patchShowing(id: string, patch: Partial<LocalShowing>, expectedGeneration?: number) {
    const item = this.showings.find((showingItem) => showingItem.id === id)!;
    if (expectedGeneration !== undefined && item.generation !== expectedGeneration) return false;
    Object.assign(item, patch); item.generation += 1; return true;
  }
  async patchMedia(id: string, patch: Partial<LocalMedia>) { Object.assign(this.media.find((item) => item.id === id)!, patch); }
  async patchMarker(id: string, patch: Partial<LocalMarker>) { Object.assign(this.markers.find((item) => item.id === id)!, patch); }
}
function transport(calls: string[], uploadImpl?: () => Promise<void>, markerImpl?: (clientId: string) => Promise<{ id: string; client_id: string }>): SyncTransport {
  return {
    async createShowing() { calls.push('create'); return { id: 'remote-1' }; },
    async presignMedia(_visit, item) { calls.push(`presign:${item.timestampOffsetMs}`); return { media_id: `remote-media-${item.timestampOffsetMs}`, upload_url: `https://upload/${item.timestampOffsetMs}`, headers: {}, expires_in: 900 }; },
    async uploadFile(url) { calls.push(`put:${url.split('/').pop()}`); await uploadImpl?.(); },
    async completeMedia(_visit, id) { calls.push(`complete:${id.split('-').pop()}`); },
    async createMarker(_visit, item) { calls.push(`marker:${item.timestampOffsetMs}:${item.clientId}`); return markerImpl ? markerImpl(item.clientId) : { id: `remote-marker-${item.clientId}`, client_id: item.clientId }; },
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

  test('a permanently rejected photo does not block the showing from finishing', async () => {
    const audio = media('audio', 1);
    const oversized = media('video', 2, { kind: 'video', contentType: 'video/mp4', timestampOffsetMs: 9_000 });
    const store = new MemoryStore([showing()], [audio, oversized]); const calls: string[] = [];
    const rejecting = transport(calls);
    rejecting.completeMedia = async (_visit, id) => {
      calls.push(`complete:${id.split('-').pop()}`);
      if (id.endsWith('9000')) throw Object.assign(new Error('media exceeds the limit'), { status: 422 });
    };

    await new SyncEngine(store, rejecting, { isOnline: async () => true }).run();

    // One unacceptable capture must not strand every other one behind it.
    expect(oversized.state).toBe('rejected');
    expect(calls).toContain('finish');
    expect(store.showings[0]!.syncState).toBe('processing');
    // ...but the agent has to be told the report is missing it.
    expect(store.showings[0]!.rejectedMediaCount).toBe(1);
  });

  test('records nothing dropped when every capture is accepted', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); const calls: string[] = [];

    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();

    expect(store.showings[0]!.rejectedMediaCount).toBe(0);
  });

  test('stops retrying a rejected item instead of queueing it forever', async () => {
    const oversized = media('video', 1, { kind: 'video', contentType: 'video/mp4', timestampOffsetMs: 9_000 });
    const store = new MemoryStore([showing()], [media('audio', 0), oversized]); const calls: string[] = [];
    const rejecting = transport(calls);
    rejecting.completeMedia = async (_visit, id) => {
      calls.push(`complete:${id.split('-').pop()}`);
      if (id.endsWith('9000')) throw Object.assign(new Error('nope'), { status: 422 });
    };
    const engine = new SyncEngine(store, rejecting, { isOnline: async () => true });

    await engine.run();
    const afterFirst = calls.filter((call) => call.startsWith('put:')).length;
    await engine.run();

    expect(calls.filter((call) => call.startsWith('put:')).length).toBe(afterFirst);
    expect(oversized.attemptCount).toBe(0);
  });

  test('keeps retrying a rate limit rather than discarding the capture', async () => {
    const throttled = media('photo', 2, { kind: 'photo', contentType: 'image/jpeg', timestampOffsetMs: 4_000 });
    const store = new MemoryStore([showing()], [media('audio', 1), throttled]); const calls: string[] = [];
    const limited = transport(calls);
    limited.completeMedia = async (_visit, id) => {
      calls.push(`complete:${id.split('-').pop()}`);
      if (id.endsWith('4000')) throw Object.assign(new Error('slow down'), { status: 429 });
    };

    await new SyncEngine(store, limited, { isOnline: async () => true }).run();

    // A rate limit is transient; discarding a real capture over one would be
    // data loss, not resilience.
    expect(throttled.state).toBe('failed');
    expect(throttled.attemptCount).toBe(1);
  });

  test('a rejected audio still blocks finishing, because it is the recording', async () => {
    const audio = media('audio', 1);
    const store = new MemoryStore([showing()], [audio]); const calls: string[] = [];
    const rejecting = transport(calls);
    rejecting.completeMedia = async () => { throw Object.assign(new Error('bad audio'), { status: 415 }); };

    await new SyncEngine(store, rejecting, { isOnline: async () => true }).run();

    expect(audio.state).toBe('rejected');
    expect(calls).not.toContain('finish');
    expect(store.showings[0]!.lastError).toBe('missing_audio');
  });

  test('syncs a property-free showing through create, upload, and finish', async () => {
    const propertyFree = showing({ subjectId: null, address: null });
    const store = new MemoryStore([propertyFree], [media('audio', 1)]); const calls: string[] = [];
    const syncTransport = transport(calls); const inputs: Parameters<typeof syncTransport.createShowing>[0][] = [];
    const createShowing = syncTransport.createShowing;
    syncTransport.createShowing = async (input) => { inputs.push(input); return createShowing(input); };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true }).run();

    // The tour time is the locally recorded start, not the moment this sync
    // ran, so a showing captured offline still reports the day it happened.
    expect(inputs).toEqual([{
      subjectId: null, address: null, contactId: null, captureClientId: 'local-1',
      startedAt: propertyFree.startedAt, captureTimezone: expect.any(String),
    }]);
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
    const existing = media('audio', 1, { remoteMediaId: 'remote-media-0', uploadUrl: 'https://upload/0', uploadExpiresAt: Date.now() + 900_000, state: 'uploading' });
    const store = new MemoryStore([showing({ remoteId: 'remote-1' })], [existing]); const calls: string[] = [];
    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();
    expect(calls).toEqual(['put:0', 'complete:0', 'finish']); expect(store.media).toHaveLength(1); expect(existing.state).toBe('completed');
  });

  test('retries an ambiguous initial presign with the stable local media identity', async () => {
    const existing = media('media-local-1', 1);
    const store = new MemoryStore([showing({ remoteId: 'remote-1' })], [existing]);
    const calls: string[] = []; const requests: { clientId: string; mediaId?: string }[] = [];
    let now = 10_000; let presignRequests = 0;
    const syncTransport = transport(calls);
    syncTransport.presignMedia = async (_visit, item) => {
      requests.push({ clientId: item.clientId, mediaId: item.mediaId });
      presignRequests += 1;
      if (presignRequests === 1) throw new Error('response lost after commit');
      return { media_id: 'remote-media-1', upload_url: 'https://upload/0', headers: {}, expires_in: 900 };
    };
    const engine = new SyncEngine(store, syncTransport, { isOnline: async () => true, now: () => now, baseRetryMs: 1_000 });

    await engine.run();
    expect(existing.state).toBe('failed');
    now = 11_000;
    await engine.run();

    expect(requests).toEqual([
      { clientId: 'media-local-1', mediaId: undefined },
      { clientId: 'media-local-1', mediaId: undefined },
    ]);
    expect(store.media).toHaveLength(1);
    expect(existing).toMatchObject({ remoteMediaId: 'remote-media-1', state: 'completed' });
  });

  test('presigns and completes captured video in the durable media order', async () => {
    const video = media('video', 2, { kind: 'video', contentType: 'video/mp4', timestampOffsetMs: 3_000 });
    const store = new MemoryStore([showing()], [media('audio', 1), video]); const calls: string[] = [];
    const syncTransport = transport(calls); const kinds: string[] = [];
    const presign = syncTransport.presignMedia;
    syncTransport.presignMedia = async (visitId, item) => { kinds.push(item.kind); return presign(visitId, item); };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true }).run();

    expect(kinds).toEqual(['audio', 'video']);
    expect(calls).toEqual(['create', 'presign:0', 'put:0', 'complete:0', 'presign:3000', 'put:3000', 'complete:3000', 'finish']);
    expect(video.state).toBe('completed');
  });

  test('syncs voice tags after the remote visit and before finish', async () => {
    const showingMarker = marker('marker-local-1', 2);
    const store = new MemoryStore([showing()], [media('audio', 1)], [showingMarker]); const calls: string[] = [];

    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();

    expect(calls).toEqual([
      'create', 'presign:0', 'put:0', 'complete:0', 'marker:2000:marker-local-1', 'finish',
    ]);
    expect(showingMarker).toMatchObject({ state: 'synced', remoteMarkerId: 'remote-marker-marker-local-1' });
  });

  test('retries an ambiguous marker request with the same client id and only finishes after acknowledgement', async () => {
    const showingMarker = marker('marker-retry', 2); const store = new MemoryStore([showing()], [media('audio', 1)], [showingMarker]);
    const calls: string[] = []; let now = 10_000; let requests = 0;
    const syncTransport = transport(calls, undefined, async (clientId) => {
      requests += 1;
      if (requests === 1) throw new Error('response lost after commit');
      return { id: 'remote-marker-committed', client_id: clientId };
    });
    const engine = new SyncEngine(store, syncTransport, { isOnline: async () => true, now: () => now, baseRetryMs: 1_000 });

    await engine.run();
    expect(showingMarker).toMatchObject({ state: 'failed', attemptCount: 1, nextAttemptAt: 11_000 });
    expect(calls).not.toContain('finish');
    now = 11_000;
    await engine.run();

    expect(calls.filter((call) => call.startsWith('marker:'))).toEqual([
      'marker:2000:marker-retry', 'marker:2000:marker-retry',
    ]);
    expect(showingMarker).toMatchObject({ state: 'synced', remoteMarkerId: 'remote-marker-committed' });
    expect(calls.filter((call) => call === 'finish')).toHaveLength(1);
  });

  test('leaves photo/video-only finished captures retryable with missing_audio', async () => {
    const photo = media('photo', 1, { kind: 'photo', contentType: 'image/jpeg' });
    const store = new MemoryStore([showing()], [photo]); const calls: string[] = [];

    await new SyncEngine(store, transport(calls), { isOnline: async () => true }).run();

    expect(photo.state).toBe('completed');
    expect(store.showings[0]).toMatchObject({ syncState: 'failed', lastError: 'missing_audio' });
    expect(calls).not.toContain('finish');
  });

  test('does not overwrite a newer finish mutation observed during remote finish', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); const calls: string[] = [];
    const syncTransport = transport(calls);
    syncTransport.finishShowing = async () => {
      calls.push('finish');
      const current = store.showings[0]!;
      current.finishRequested = false;
      current.syncState = 'local';
      current.generation += 1;
    };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true }).run();

    expect(store.showings[0]).toMatchObject({ finishRequested: false, syncState: 'local' });
    expect(store.showings[0]!.processingStatus).toBeNull();
  });

  test('refreshes an expired presign without creating another local media item', async () => {
    const existing = media('audio', 1, {
      remoteMediaId: 'remote-media-old', uploadUrl: 'https://upload/old',
      uploadExpiresAt: 9_000, state: 'queued',
    });
    const store = new MemoryStore([showing({ remoteId: 'remote-1' })], [existing]); const calls: string[] = [];
    const syncTransport = transport(calls);
    syncTransport.presignMedia = async (_visit, item) => {
      calls.push(`refresh:${item.mediaId}`);
      return { media_id: item.mediaId ?? 'remote-media-new', upload_url: 'https://upload/new', headers: {}, expires_in: 900 };
    };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true, now: () => 10_000 }).run();

    expect(calls).toContain('refresh:remote-media-old');
    expect(store.media).toHaveLength(1);
    expect(existing.remoteMediaId).toBe('remote-media-old');
    expect(existing.state).toBe('completed');
  });

  test('retries an ambiguous visit create with the same capture idempotency key', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); const calls: string[] = [];
    const syncTransport = transport(calls); const keys: (string | undefined)[] = [];
    let requests = 0;
    syncTransport.createShowing = async (input) => {
      keys.push(input.captureClientId);
      requests += 1;
      if (requests === 1) throw new Error('response lost after commit');
      return { id: 'remote-1' };
    };
    const engine = new SyncEngine(store, syncTransport, { isOnline: async () => true });

    await engine.run();
    expect(store.showings[0]).toMatchObject({ syncState: 'failed' });
    expect(calls).not.toContain('finish');
    await engine.run();

    expect(keys).toEqual(['local-1', 'local-1']);
    expect(store.showings[0]!.syncState).toBe('processing');
  });

  test('refreshes once when an upload rejects an expired presign response', async () => {
    const store = new MemoryStore([showing()], [media('audio', 1)]); const calls: string[] = [];
    const syncTransport = transport(calls); let uploads = 0;
    syncTransport.uploadFile = async (url) => {
      uploads += 1;
      calls.push(`put:${url.split('/').pop()}`);
      if (uploads === 1) throw Object.assign(new Error('signature expired'), { status: 403 });
    };

    await new SyncEngine(store, syncTransport, { isOnline: async () => true }).run();

    expect(calls.filter((call) => call.startsWith('presign:'))).toHaveLength(2);
    expect(calls.filter((call) => call.startsWith('put:'))).toHaveLength(2);
    expect(store.media[0]!.state).toBe('completed');
  });
});
