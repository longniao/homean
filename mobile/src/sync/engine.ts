import type { LocalMarker, LocalMedia, LocalShowing, MediaKind, SyncState } from '../types';

type ShowingPatch = Partial<Pick<LocalShowing, 'remoteId' | 'syncState' | 'processingStatus' | 'lastError' | 'updatedAt'>>;

export interface SyncStore {
  getShowing(id: string): Promise<LocalShowing | null>;
  pendingShowings(): Promise<LocalShowing[]>;
  mediaForShowing(showingId: string): Promise<LocalMedia[]>;
  markersForShowing(showingId: string): Promise<LocalMarker[]>;
  patchShowing(id: string, patch: ShowingPatch, expectedGeneration?: number): Promise<boolean>;
  patchMedia(id: string, patch: Partial<Pick<LocalMedia, 'remoteMediaId' | 'state' | 'attemptCount' | 'nextAttemptAt' | 'uploadUrl' | 'uploadHeaders' | 'uploadExpiresAt'>>): Promise<void>;
  patchMarker(id: string, patch: Partial<Pick<LocalMarker, 'remoteMarkerId' | 'state' | 'attemptCount' | 'nextAttemptAt' | 'lastError'>>): Promise<void>;
}

export interface SyncTransport {
  createShowing(input: { subjectId: string | null; address: string | null; contactId: string | null; consentAck?: boolean; captureClientId?: string; startedAt?: number; captureTimezone?: string }): Promise<{ id: string }>;
  presignMedia(visitId: string, media: { clientId: string; mediaId?: string; kind: MediaKind; contentType: string; timestampOffsetMs: number }): Promise<{ media_id: string; upload_url: string; headers: Record<string, string>; expires_at?: string; expires_in?: number }>;
  uploadFile(url: string, headers: Record<string, string>, fileUri: string): Promise<void>;
  completeMedia(visitId: string, mediaId: string): Promise<void>;
  createMarker(visitId: string, marker: { clientId: string; markerType: 'voice_tag'; timestampOffsetMs: number }): Promise<{ id: string; client_id: string }>;
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

  /** The device zone, which is where the tour happened. Undefined if unresolvable. */
  private timezone(): string | undefined {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
    } catch {
      return undefined;
    }
  }

  async run(): Promise<void> {
    if (this.running || !(await this.options.isOnline())) return;
    this.running = true;
    try {
      for (const showing of await this.store.pendingShowings()) await this.syncShowing(showing);
    } finally { this.running = false; }
  }

  private async syncShowing(snapshot: LocalShowing): Promise<void> {
    let current = await this.store.getShowing(snapshot.id);
    if (!current) return;

    // The generation is a local optimistic-concurrency token.  Any capture
    // mutation (new media, marker, or finish request) increments it.  We only
    // write showing state when the token we observed is still current.
    if (!await this.store.patchShowing(snapshot.id, { syncState: 'syncing', lastError: null, updatedAt: this.now() }, current.generation)) return;
    current = await this.store.getShowing(snapshot.id);
    if (!current) return;
    let generation = current.generation;
    let remoteId = current.remoteId;

    try {
      if (!remoteId) {
        const input = {
          subjectId: current.subjectId,
          address: current.address,
          contactId: current.contactId,
          captureClientId: current.id,
          // Recorded locally when the tour began, which for a queued offline
          // showing is well before this request.
          startedAt: current.startedAt,
          captureTimezone: this.timezone(),
          ...(current.consentAck === undefined ? {} : { consentAck: current.consentAck }),
        };
        remoteId = (await this.transport.createShowing(input)).id;
        // If a user mutation occurred while the request was in flight, leave
        // the newer local generation untouched.  The idempotency key makes it
        // safe to retry this acknowledgement on the next run.
        if (!await this.store.patchShowing(snapshot.id, { remoteId, updatedAt: this.now() }, generation)) return;
        current = await this.store.getShowing(snapshot.id);
        if (!current) return;
        generation = current.generation;
        remoteId = current.remoteId ?? remoteId;
      }

      await this.syncPendingMedia(remoteId, snapshot.id);
      await this.syncPendingMarkers(remoteId, snapshot.id);

      // Reread all durable state after child work.  The initial showing
      // snapshot may be stale by now; a CAS below prevents a late write from
      // masking a concurrent media/marker/finish mutation.
      current = await this.store.getShowing(snapshot.id);
      if (!current || current.generation !== generation) return;
      const media = await this.store.mediaForShowing(snapshot.id);
      const markers = await this.store.markersForShowing(snapshot.id);
      if (media.some((item) => item.state !== 'completed') || markers.some((item) => item.state !== 'synced')) return;

      if (current.finishRequested) {
        if (!media.some((item) => item.kind === 'audio' && item.state === 'completed')) {
          await this.store.patchShowing(snapshot.id, { syncState: 'failed', lastError: 'missing_audio', updatedAt: this.now() }, generation);
          return;
        }
        await this.transport.finishShowing(remoteId);
        await this.store.patchShowing(snapshot.id, { syncState: 'processing', processingStatus: 'queued', lastError: null, updatedAt: this.now() }, generation);
      } else {
        await this.store.patchShowing(snapshot.id, { syncState: 'synced', lastError: null, updatedAt: this.now() }, generation);
      }
    } catch (error) {
      const patch: ShowingPatch = {
        syncState: 'failed',
        lastError: error instanceof Error ? error.message : String(error),
        updatedAt: this.now(),
      };
      // Deliberately use the generation owned by this run, rather than a
      // reread here.  A newer mutation must win over an old failure result.
      await this.store.patchShowing(snapshot.id, patch, generation);
    }
  }

  private async syncPendingMedia(visitId: string, showingId: string): Promise<void> {
    for (;;) {
      const media = (await this.store.mediaForShowing(showingId)).sort((a, b) => a.createdAt - b.createdAt);
      const pending = media.filter((item) => item.state !== 'completed');
      if (!pending.length) return;
      for (const item of pending) {
        if (item.nextAttemptAt > this.now()) throw new DeferredRetryError();
        await this.syncMedia(visitId, item);
      }
    }
  }

  private async syncPendingMarkers(visitId: string, showingId: string): Promise<void> {
    for (;;) {
      const markers = (await this.store.markersForShowing(showingId)).sort((a, b) => a.createdAt - b.createdAt);
      const pending = markers.filter((item) => item.state !== 'synced');
      if (!pending.length) return;
      for (const item of pending) {
        if (item.nextAttemptAt > this.now()) throw new DeferredRetryError();
        await this.syncMarker(visitId, item);
      }
    }
  }

  private async syncMedia(visitId: string, item: LocalMedia): Promise<void> {
    try {
      let mediaId = item.remoteMediaId;
      let uploadUrl = item.uploadUrl;
      let headers = item.uploadHeaders;
      let uploadExpiresAt = item.uploadExpiresAt;
      const needsPresign = !mediaId || !uploadUrl || (item.state !== 'uploaded' && (!uploadExpiresAt || uploadExpiresAt <= this.now() + 5_000));
      if (needsPresign) {
        ({ mediaId, uploadUrl, headers, uploadExpiresAt } = await this.presignMedia(visitId, item, mediaId ?? undefined));
      }
      if (!mediaId || !uploadUrl) throw new Error('presign did not return a media id and upload URL');
      if (item.state !== 'uploaded') {
        let refreshed = false;
        for (;;) {
          try {
            await this.store.patchMedia(item.id, { state: 'uploading' });
            await this.transport.uploadFile(uploadUrl, headers, item.fileUri);
            break;
          } catch (error) {
            if (refreshed || !this.isExpiredPresignError(error)) throw error;
            refreshed = true;
            ({ mediaId, uploadUrl, headers, uploadExpiresAt } = await this.presignMedia(visitId, item, mediaId));
          }
        }
        await this.store.patchMedia(item.id, { state: 'uploaded' });
      }
      await this.transport.completeMedia(visitId, mediaId);
      await this.store.patchMedia(item.id, { state: 'completed', nextAttemptAt: 0, uploadExpiresAt });
    } catch (error) {
      const attempts = item.attemptCount + 1;
      await this.store.patchMedia(item.id, {
        state: 'failed', attemptCount: attempts,
        nextAttemptAt: this.now() + this.baseRetryMs * 2 ** Math.min(attempts - 1, 8),
      });
      throw error;
    }
  }

  private async presignMedia(visitId: string, item: LocalMedia, mediaId?: string): Promise<{ mediaId: string; uploadUrl: string; headers: Record<string, string>; uploadExpiresAt: number }> {
    const presigned = await this.transport.presignMedia(visitId, { clientId: item.id, mediaId, kind: item.kind, contentType: item.contentType, timestampOffsetMs: item.timestampOffsetMs });
    const expiresAt = presigned.expires_at ? Date.parse(presigned.expires_at) : this.now() + (presigned.expires_in ?? 900) * 1_000;
    if (!Number.isFinite(expiresAt)) throw new Error('presign returned an invalid expiry');
    await this.store.patchMedia(item.id, { remoteMediaId: presigned.media_id, uploadUrl: presigned.upload_url, uploadHeaders: presigned.headers, uploadExpiresAt: expiresAt, state: 'presigned' });
    return { mediaId: presigned.media_id, uploadUrl: presigned.upload_url, headers: presigned.headers, uploadExpiresAt: expiresAt };
  }

  private isExpiredPresignError(error: unknown): boolean {
    const status = (error as { status?: unknown })?.status;
    if (status === 401 || status === 403) return true;
    return /expired|presign|signature|request.?time/i.test(error instanceof Error ? error.message : String(error));
  }

  private async syncMarker(visitId: string, item: LocalMarker): Promise<void> {
    try {
      await this.store.patchMarker(item.id, { state: 'syncing', lastError: null });
      const marker = await this.transport.createMarker(visitId, {
        clientId: item.id,
        markerType: item.markerType,
        timestampOffsetMs: item.timestampOffsetMs,
      });
      await this.store.patchMarker(item.id, {
        remoteMarkerId: marker.id,
        state: 'synced',
        attemptCount: item.attemptCount,
        nextAttemptAt: 0,
        lastError: null,
      });
    } catch (error) {
      const attempts = item.attemptCount + 1;
      await this.store.patchMarker(item.id, {
        state: 'failed',
        attemptCount: attempts,
        nextAttemptAt: this.now() + this.baseRetryMs * 2 ** Math.min(attempts - 1, 8),
        lastError: error instanceof Error ? error.message : String(error),
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
