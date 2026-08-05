export type SyncState = 'local' | 'syncing' | 'synced' | 'processing' | 'ready' | 'failed';
export type MediaState = 'queued' | 'presigned' | 'uploading' | 'uploaded' | 'completed' | 'failed';
export type MediaKind = 'audio' | 'photo';

export interface TokenPair { accessToken: string; refreshToken: string; expiresAt: number }

export interface Contact { id: string; name: string; email: string | null }
export interface Property { id: string; displayName: string; address: string }
export interface Observation {
  id: string; zoneId: string | null; category: string; content: string;
  sourceTranscriptSegmentId: string | null; timestampStart: number | null;
  flags: { sensitive?: boolean; reason?: string | null; suggested_rewrite?: string | null };
  reviewStatus: string;
}
export interface ReportBullet { text: string; observation_ids: string[] }
export interface RoomSection { zone_id: string | null; zone_type: string | null; bullets: ReportBullet[] }
export interface ReportContent {
  executive_summary: string; room_by_room: RoomSection[]; highlights: ReportBullet[];
  concerns: ReportBullet[]; follow_ups: ReportBullet[];
}
export interface ShowingSummary {
  id: string; status: string; processingStatus: string; createdAt: string;
  property: Property | null; contact: Contact | null;
}
export interface ShowingDetail extends ShowingSummary {
  observations: Observation[];
  report: { id: string; content: ReportContent; status: string } | null;
}
export interface LocalShowing {
  id: string; remoteId: string | null; contactId: string | null; subjectId: string | null;
  address: string | null; title: string; startedAt: number; endedAt: number | null;
  elapsedMs: number; syncState: SyncState; processingStatus: string | null;
  finishRequested: boolean; lastError: string | null; updatedAt: number;
}
export interface LocalMedia {
  id: string; showingId: string; remoteMediaId: string | null; kind: MediaKind;
  fileUri: string; contentType: string; timestampOffsetMs: number; state: MediaState;
  attemptCount: number; nextAttemptAt: number; uploadUrl: string | null;
  uploadHeaders: Record<string, string>; createdAt: number;
}
