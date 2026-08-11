export type SyncState = 'local' | 'syncing' | 'synced' | 'processing' | 'ready' | 'failed';
export type MediaState = 'queued' | 'presigned' | 'uploading' | 'uploaded' | 'completed' | 'failed';
export type MediaKind = 'audio' | 'photo' | 'video';
export type MarkerState = 'queued' | 'syncing' | 'synced' | 'failed';

export interface TokenPair { accessToken: string; refreshToken: string; expiresAt: number }

export interface Contact { id: string; name: string; email: string | null }
export interface Property { id: string; displayName: string; address: string }
export interface VerticalDisplayLabels {
  zones: Record<string, string>;
  observations: Record<string, string>;
}
export interface VerticalConfig {
  zoneTaxonomy: string[];
  observationSchema: string[];
  displayLabels: VerticalDisplayLabels;
}
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
  property: Property | null; contact: Contact | null; consentAck?: boolean;
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
  generation: number;
  consentAck?: boolean;
}
export interface LocalMedia {
  id: string; showingId: string; remoteMediaId: string | null; kind: MediaKind;
  fileUri: string; contentType: string; timestampOffsetMs: number; state: MediaState;
  attemptCount: number; nextAttemptAt: number; uploadUrl: string | null;
  uploadHeaders: Record<string, string>; uploadExpiresAt: number | null; createdAt: number;
  /** Present for audio recovered from an interrupted recording. */
  recoveryKey?: string | null;
}
export interface LocalMarker {
  id: string; showingId: string; remoteMarkerId: string | null; markerType: 'voice_tag';
  timestampOffsetMs: number; state: MarkerState; attemptCount: number; nextAttemptAt: number;
  lastError: string | null; createdAt: number;
}
