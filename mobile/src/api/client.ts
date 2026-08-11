import { File } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';
import { z } from 'zod';
import { clearTokens, getTokens, setTokens } from '../auth/tokenStore';
import type { Contact, Property, ReportContent, ShowingDetail, ShowingSummary, TokenPair } from '../types';

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: string) { super(detail); }
}

const tokenSchema = z.object({
  access_token: z.string(), refresh_token: z.string(), expires_in: z.number(),
});
const contactSchema = z.object({ id: z.string(), name: z.string(), email: z.string().nullable() });
const propertySchema = z.object({ id: z.string(), display_name: z.string(), address: z.string() });
const observationSchema = z.object({
  id: z.string(), zone_id: z.string().nullable(), category: z.string(), content: z.string(),
  source_transcript_segment_id: z.string().nullable(), timestamp_start: z.number().nullable(),
  flags: z.record(z.string(), z.unknown()), review_status: z.string(),
});
const bulletSchema = z.object({ text: z.string(), observation_ids: z.array(z.string()) });
const reportContentSchema = z.object({
  executive_summary: z.string(),
  room_by_room: z.array(z.object({ zone_id: z.string().nullable(), zone_type: z.string().nullable(), bullets: z.array(bulletSchema) })),
  highlights: z.array(bulletSchema), concerns: z.array(bulletSchema), follow_ups: z.array(bulletSchema),
});
const reportSchema = z.object({ id: z.string(), content: reportContentSchema, status: z.string() });
const showingSchema = z.object({
  id: z.string(), status: z.string(), processing_status: z.string(), created_at: z.string(),
  property: propertySchema.nullable(), contact: contactSchema.nullable(),
  consent_ack: z.boolean().optional().default(false),
});
const showingDetailSchema = showingSchema.extend({ observations: z.array(observationSchema), report: reportSchema.nullable() });

function tokensFromWire(value: z.infer<typeof tokenSchema>): TokenPair {
  return { accessToken: value.access_token, refreshToken: value.refresh_token, expiresAt: Date.now() + value.expires_in * 1000 };
}
function contactFromWire(value: z.infer<typeof contactSchema>): Contact {
  return { id: value.id, name: value.name, email: value.email };
}
function propertyFromWire(value: z.infer<typeof propertySchema>): Property {
  return { id: value.id, displayName: value.display_name, address: value.address };
}
function showingFromWire(value: z.infer<typeof showingSchema>): ShowingSummary {
  return { id: value.id, status: value.status, processingStatus: value.processing_status, createdAt: value.created_at, property: value.property ? propertyFromWire(value.property) : null, contact: value.contact ? contactFromWire(value.contact) : null, consentAck: value.consent_ack };
}

async function responseDetail(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg).filter(Boolean).join(', ');
  } catch { /* the response is not JSON */ }
  return `HTTP ${response.status}`;
}

export class ApiClient {
  private refreshPromise: Promise<TokenPair> | null = null;

  async login(email: string, password: string): Promise<void> {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
    });
    if (!response.ok) throw new ApiError(response.status, await responseDetail(response));
    await setTokens(tokensFromWire(tokenSchema.parse(await response.json())));
  }

  async logout(): Promise<void> { await clearTokens(); }

  private async refresh(refreshToken: string): Promise<TokenPair> {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) { await clearTokens(); throw new ApiError(response.status, await responseDetail(response)); }
    const tokens = tokensFromWire(tokenSchema.parse(await response.json()));
    await setTokens(tokens);
    return tokens;
  }

  private async accessToken(forceRefresh = false): Promise<string> {
    const tokens = await getTokens();
    if (!tokens) throw new ApiError(401, 'Not authenticated');
    if (!forceRefresh && tokens.expiresAt > Date.now() + 30_000) return tokens.accessToken;
    this.refreshPromise ??= this.refresh(tokens.refreshToken).finally(() => { this.refreshPromise = null; });
    return (await this.refreshPromise).accessToken;
  }

  private async request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
    const token = await this.accessToken();
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers, Authorization: `Bearer ${token}` },
    });
    if (response.status === 401 && retry) {
      await this.accessToken(true);
      return this.request(path, init, false);
    }
    if (!response.ok) throw new ApiError(response.status, await responseDetail(response));
    return response;
  }

  async listContacts(): Promise<Contact[]> {
    return z.array(contactSchema).parse(await (await this.request('/contacts')).json()).map(contactFromWire);
  }
  async listProperties(): Promise<Property[]> {
    return z.array(propertySchema).parse(await (await this.request('/properties')).json()).map(propertyFromWire);
  }
  async listShowings(): Promise<ShowingSummary[]> {
    const body = z.object({ items: z.array(showingSchema) }).parse(await (await this.request('/showings?limit=50')).json());
    return body.items.map(showingFromWire);
  }
  async createShowing(input: { subjectId: string | null; address: string | null; contactId: string | null; consentAck?: boolean }): Promise<ShowingSummary> {
    const payload: { subject_id?: string; address?: string; contact_id: string | null; consent_ack?: boolean } = { contact_id: input.contactId };
    if (input.consentAck !== undefined) payload.consent_ack = input.consentAck;
    if (input.subjectId) payload.subject_id = input.subjectId;
    else if (input.address) payload.address = input.address;
    const body = showingSchema.parse(await (await this.request('/showings', { method: 'POST', body: JSON.stringify(payload) })).json());
    return showingFromWire(body);
  }
  async getShowing(id: string): Promise<ShowingDetail> {
    const value = showingDetailSchema.parse(await (await this.request(`/showings/${id}`)).json());
    return {
      ...showingFromWire(value),
      observations: value.observations.map((item) => ({
        id: item.id, zoneId: item.zone_id, category: item.category, content: item.content,
        sourceTranscriptSegmentId: item.source_transcript_segment_id, timestampStart: item.timestamp_start,
        flags: item.flags, reviewStatus: item.review_status,
      })),
      report: value.report ? { id: value.report.id, content: value.report.content, status: value.report.status } : null,
    };
  }
  async presignMedia(visitId: string, media: { kind: 'audio' | 'photo'; contentType: string; timestampOffsetMs: number }) {
    return z.object({ media_id: z.string(), upload_url: z.string(), headers: z.record(z.string(), z.string()) }).parse(
      await (await this.request(`/showings/${visitId}/media/presign`, { method: 'POST', body: JSON.stringify({ type: media.kind, content_type: media.contentType, timestamp_offset_ms: media.timestampOffsetMs }) })).json(),
    );
  }
  async uploadFile(url: string, headers: Record<string, string>, fileUri: string): Promise<void> {
    const response = await expoFetch(url, { method: 'PUT', headers, body: new File(fileUri) });
    if (!response.ok) throw new ApiError(response.status, await responseDetail(response));
  }
  async completeMedia(visitId: string, mediaId: string): Promise<void> {
    await this.request(`/showings/${visitId}/media/${mediaId}/complete`, { method: 'POST' });
  }
  async finishShowing(visitId: string): Promise<void> {
    await this.request(`/showings/${visitId}/finish`, { method: 'POST' });
  }
  async updateReport(reportId: string, content: ReportContent): Promise<void> {
    await this.request(`/reports/${reportId}`, { method: 'PATCH', body: JSON.stringify({ content }) });
  }
  async dismissObservation(observationId: string): Promise<void> {
    await this.request(`/observations/${observationId}/dismiss`, { method: 'POST' });
  }
  async confirmShowing(visitId: string): Promise<void> {
    await this.request(`/showings/${visitId}/confirm`, { method: 'POST' });
  }
  async createShareLink(visitId: string): Promise<string> {
    const body = z.object({ share_url: z.string() }).parse(await (await this.request(`/showings/${visitId}/send`, { method: 'POST', body: JSON.stringify({ channel: 'link_only' }) })).json());
    return body.share_url;
  }
}

export const api = new ApiClient();
