import type { LocalMedia, LocalShowing, SyncState } from '../types';

export interface SyncStore {
  pendingShowings(): Promise<LocalShowing[]>;
  mediaForShowing(showingId: string): Promise<LocalMedia[]>;
  patchShowing(id: string, patch: Partial<Pick<LocalShowing, 'remoteId' | 'syncState' | 'processingStatus' | 'lastError' | 'updatedAt'>>): Promise<void>;
  patchMedia(id: string, patch: Partial<Pick<LocalMedia, 'remoteMediaId' | 'state' | 'attemptCount' | 'nextAttemptAt' | 'uploadUrl' | 'uploadHeaders'>>): Promise<void>;
}

export interface SyncTransport {
  createShowing(input: { subjectId: string | null; address: string | null; contactId: string | null; consentAck?: boolean }): Promise<{ id: string }>;
  presignMedia(visitId: string, media: { kind: 'audio' | 'photo'; contentType: string; timestampOffsetMs: number }): Promise<{ media_id: string; upload_url: string; headers: Record<string, string> }>;
  uploadFile(url: string, headers: Record<string, string>, fileUri: string): Promise<void>;
  completeMedia(visitId: string, mediaId: string): Promise<void>;
  finishShowing(visitId: string): Promise<void>;
}

export interface SyncEngineOptions {
  isOnline: () => Promise<boolean>;
  now?: () => number;
  baseRetryMs?: number;
}

export class SyncEngine {
  private running = false;
  private readonly now: () => number;
  private readonly baseRetryMs: number;

  constructor(private readonly store: SyncStore, private readonly transport: SyncTransport, private readonly options: SyncEngineOptions) {
    this.now = options.now ?? Date.now;
    this.baseRetryMs = options.baseRetryMs ?? 2_000;
  }

  async run(): Promise<void> {
    if (this.running || !(await this.options.isOnline())) return;
    this.running = true;
    try {
      for (const showing of await this.store.pendingShowings()) await this.syncShowing(showing);
    } finally { this.running = false; }
  }

  private async syncShowing(showing: LocalShowing): Promise<void> {
    let remoteId = showing.remoteId;
    try {
      await this.store.patchShowing(showing.id, { syncState: 'syncing', lastError: null, updatedAt: this.now() });
      if (!remoteId) {
        const input = { subjectId: showing.subjectId, address: showing.address, contactId: showing.contactId, ...(showing.consentAck === undefined ? {} : { consentAck: showing.consentAck }) };
        remoteId = (await this.transport.createShowing(input)).id;
        await this.store.patchShowing(showing.id, { remoteId, updatedAt: this.now() });
      }

      const media = (await this.store.mediaForShowing(showing.id)).sort((a, b) => a.createdAt - b.createdAt);
      for (const item of media) {
        if (item.state === 'completed') continue;
        if (item.nextAttemptAt > this.now()) throw new DeferredRetryError();
        await this.syncMedia(remoteId, item);
      }

      if (showing.finishRequested && media.length === 0) {
        await this.store.patchShowing(showing.id, { syncState: 'failed', lastError: 'missing_media', updatedAt: this.now() });
      } else if (showing.finishRequested) {
        await this.transport.finishShowing(remoteId);
        await this.store.patchShowing(showing.id, { syncState: 'processing', processingStatus: 'queued', updatedAt: this.now() });
      } else {
        await this.store.patchShowing(showing.id, { syncState: 'synced', updatedAt: this.now() });
      }
    } catch (error) {
      if (error instanceof DeferredRetryError) {
        await this.store.patchShowing(showing.id, { syncState: 'failed', updatedAt: this.now() });
        return;
      }
      await this.store.patchShowing(showing.id, { syncState: 'failed', lastError: error instanceof Error ? error.message : String(error), updatedAt: this.now() });
    }
  }

  private async syncMedia(visitId: string, item: LocalMedia): Promise<void> {
    try {
      let mediaId = item.remoteMediaId;
      let uploadUrl = item.uploadUrl;
      let headers = item.uploadHeaders;
      if (!mediaId || !uploadUrl) {
        const presigned = await this.transport.presignMedia(visitId, { kind: item.kind, contentType: item.contentType, timestampOffsetMs: item.timestampOffsetMs });
        mediaId = presigned.media_id; uploadUrl = presigned.upload_url; headers = presigned.headers;
        await this.store.patchMedia(item.id, { remoteMediaId: mediaId, uploadUrl, uploadHeaders: headers, state: 'presigned' });
      }
      if (item.state !== 'uploaded') {
        await this.store.patchMedia(item.id, { state: 'uploading' });
        await this.transport.uploadFile(uploadUrl, headers, item.fileUri);
        await this.store.patchMedia(item.id, { state: 'uploaded' });
      }
      await this.transport.completeMedia(visitId, mediaId);
      await this.store.patchMedia(item.id, { state: 'completed', nextAttemptAt: 0 });
    } catch (error) {
      const attempts = item.attemptCount + 1;
      await this.store.patchMedia(item.id, {
        state: 'failed', attemptCount: attempts,
        nextAttemptAt: this.now() + this.baseRetryMs * 2 ** Math.min(attempts - 1, 8),
      });
      throw error;
    }
  }
}

class DeferredRetryError extends Error {}

export function syncStateFromProcessing(remoteProcessing: string, fallback: SyncState): SyncState {
  if (remoteProcessing === 'ready') return 'ready';
  if (remoteProcessing === 'failed') return 'failed';
  if (['queued', 'transcribing', 'structuring', 'generating'].includes(remoteProcessing)) return 'processing';
  return fallback;
}
