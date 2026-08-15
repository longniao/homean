import { z } from "zod";

const nullableString = z.string().nullable();
const dateString = z.string();

export const contactSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  email: nullableString,
  phone: nullableString,
  notes: nullableString,
  created_at: dateString,
  updated_at: dateString,
});

export const propertySchema = z.object({
  id: z.string().uuid(),
  display_name: z.string(),
  address: z.string(),
  attributes: z.object({
    beds: z.number().int().nullable().optional(),
    baths: z.number().nullable().optional(),
    sqft: z.number().int().nullable().optional(),
    listing_price: z.number().nullable().optional(),
    mls_id: nullableString.optional(),
  }),
  created_at: dateString,
  updated_at: dateString,
});

const showingStatusSchema = z.enum(["draft", "confirmed", "sent_to_client"]);
export const showingSchema = z.object({
  id: z.string().uuid(),
  status: showingStatusSchema,
  processing_status: z.string(),
  processing_failed_step: nullableString,
  processing_error: nullableString,
  started_at: nullableString,
  ended_at: nullableString,
  created_at: dateString,
  updated_at: dateString,
  property: propertySchema.nullable(),
  contact: contactSchema.nullable(),
  consent_ack: z.boolean().optional(),
});

export const mediaSchema = z.object({
  id: z.string().uuid(),
  type: z.string(),
  content_type: z.string(),
  timestamp_offset_ms: z.number().nullable(),
  status: z.string(),
  size_bytes: z.number().nullable(),
  created_at: dateString,
});

export const zoneSchema = z.object({
  id: z.string().uuid(),
  zone_type: z.string(),
  position: z.number().int(),
  start_transcript_segment_id: nullableString,
  end_transcript_segment_id: nullableString,
});

export const observationSchema = z.object({
  id: z.string().uuid(),
  zone_id: nullableString,
  category: z.string(),
  content: z.string(),
  source_type: z.string(),
  source_transcript_segment_id: nullableString,
  source_media_id: nullableString,
  timestamp_start: z.number().nullable(),
  timestamp_end: z.number().nullable(),
  ai_model: nullableString,
  prompt_version: nullableString,
  confidence: z.number().nullable(),
  flags: z.record(z.string(), z.unknown()),
  review_status: z.string(),
  reviewed_by: nullableString,
  reviewed_at: nullableString,
});

export const transcriptSchema = z.object({
  id: z.string().uuid(),
  raw_media_id: z.string().uuid(),
  text: z.string(),
  original_text: nullableString,
  timestamp_start: z.number().nullable(),
  timestamp_end: z.number().nullable(),
  confidence: z.number().nullable(),
});

export const reportBulletSchema = z.object({
  text: z.string().min(1),
  observation_ids: z.array(z.string().uuid()).min(1),
});
export const reportContentSchema = z.object({
  executive_summary: z.string(),
  room_by_room: z.array(
    z.object({
      zone_id: nullableString,
      zone_type: nullableString,
      bullets: z.array(reportBulletSchema),
    }),
  ),
  highlights: z.array(reportBulletSchema),
  concerns: z.array(reportBulletSchema),
  follow_ups: z.array(reportBulletSchema),
});
export const reportSchema = z.object({
  id: z.string().uuid(),
  template_id: z.string(),
  content: reportContentSchema,
  rendered_html: nullableString,
  status: z.string(),
});

export const markerSchema = z.object({
  id: z.string(),
  marker_type: z.literal("voice_tag"),
  timestamp_offset_ms: z.number(),
  // Null when the tap fell after the last thing said, so it bookmarks nothing.
  transcript_segment_id: z.string().nullable().catch(null),
  created_at: dateString,
});

const showingDetailSchema = showingSchema.extend({
  media: z.array(mediaSchema),
  zones: z.array(zoneSchema),
  observations: z.array(observationSchema),
  transcript: z.array(transcriptSchema),
  markers: z.array(markerSchema).default([]),
  report: reportSchema.nullable(),
});

export const showingListSchema = z.object({
  items: z.array(showingSchema),
  next_cursor: nullableString,
});

export const meSchema = z.object({
  user: z.object({
    id: z.string().uuid(),
    email: z.string().email(),
    name: nullableString,
    phone: nullableString,
  }),
  workspace: z.object({ id: z.string().uuid(), name: z.string(), language: z.string() }),
  profile: z.object({ id: z.string().uuid(), role: z.string(), vertical: z.string() }),
});

export const brandingSchema = z.object({
  id: nullableString,
  logo_key: nullableString,
  display_name: nullableString,
  phone: nullableString,
  email: nullableString,
  license_no: nullableString,
  accent_color: z.string(),
  updated_at: nullableString,
});

export const verticalConfigSchema = z.object({
  zone_taxonomy: z.array(z.string()),
  observation_schema: z.array(z.string()),
  display_labels: z.object({
    zones: z.record(z.string(), z.string()),
    observations: z.record(z.string(), z.string()),
  }),
  // Optional so an older API still parses; the form then falls back to its
  // bundled wording and records the version as unknown.
  consent: z.object({ version: z.string(), text: z.string() }).optional(),
});

export const deliverySchema = z.object({
  share_links: z.array(
    z.object({
      id: z.string().uuid(),
      token: z.string(),
      url: z.string(),
      created_at: dateString,
      expires_at: nullableString,
      revoked: z.boolean(),
      open_count: z.number().int().nonnegative(),
    }),
  ),
  sends: z.array(
    z.object({
      send_id: z.string().uuid(),
      channel: z.string(),
      to_email: nullableString,
      status: z.enum(["pending", "sent", "failed", "outcome_unknown"]),
      attempt_count: z.number().int().nonnegative(),
      last_attempt_at: nullableString,
      sent_at: dateString,
      error: nullableString,
    }),
  ),
});

export const billingSchema = z.object({
  workspace_id: z.string().uuid(),
  plan: z.enum(["trial", "solo_monthly"]),
  status: z.string(),
  active: z.boolean(),
  billing_action: z.enum(["subscribe", "manage_billing"]),
  can_checkout: z.boolean(),
  can_portal: z.boolean(),
  stripe_customer_attached: z.boolean(),
  trial_ends_at: nullableString,
  current_period_end: nullableString,
  cancel_at_period_end: z.boolean(),
});

export type Contact = z.infer<typeof contactSchema>;
export type Property = z.infer<typeof propertySchema>;
export type Showing = z.infer<typeof showingSchema>;
export type ShowingList = z.infer<typeof showingListSchema>;
export type ShowingDetail = z.infer<typeof showingDetailSchema>;
export type Observation = z.infer<typeof observationSchema>;
export type TranscriptSegment = z.infer<typeof transcriptSchema>;
export type ReportContent = z.infer<typeof reportContentSchema>;
export type ReportBullet = z.infer<typeof reportBulletSchema>;
export type Branding = z.infer<typeof brandingSchema>;
export type VerticalConfig = z.infer<typeof verticalConfigSchema>;
export type Delivery = z.infer<typeof deliverySchema>;
export type BillingStatus = z.infer<typeof billingSchema>;

export function dedupeShowingsById(showings: Showing[]): Showing[] {
  const seen = new Set<string>();
  return showings.filter((showing) => {
    if (seen.has(showing.id)) return false;
    seen.add(showing.id);
    return true;
  });
}

export function getPublicReportPdfUrl(shareUrl: string): string | null {
  try {
    const url = new URL(shareUrl);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    const match = url.pathname.match(/^\/r\/([^/]+)\/?$/);
    if (!match) return null;
    url.pathname = `/r/${match[1]}/pdf`;
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public payload: unknown,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const message =
      typeof payload === "object" && payload && "detail" in payload
        ? String(payload.detail)
        : `Request failed (${response.status})`;
    throw new ApiError(response.status, message, payload);
  }
  return schema.parse(payload);
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`/api/backend${path}`);
  const payload = await response.text();
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed (${response.status})`, payload);
  }
  return payload;
}

function json(method: string, body?: unknown): RequestInit {
  return { method, body: body === undefined ? undefined : JSON.stringify(body) };
}

/** Undefined when the runtime cannot resolve a zone, which the API treats as UTC. */
function browserTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

export type ShowingFilters = {
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  contactId?: string;
  subjectId?: string;
  unassigned?: boolean;
  query?: string;
  cursor?: string;
  limit?: number;
};

export const api = {
  billing: {
    get: () => request("/billing", billingSchema),
    checkout: () => request("/billing/checkout", z.object({ url: z.string().url() }), json("POST", { plan: "solo_monthly" })),
    portal: () => request("/billing/portal", z.object({ url: z.string().url() }), json("POST")),
  },
  me: () => request("/me", meSchema),
  updateMe: (body: { name: string | null }) => request("/me", meSchema, json("PATCH", body)),
  contacts: {
    list: () => request("/contacts", z.array(contactSchema)),
    get: (id: string) => request(`/contacts/${id}`, contactSchema),
    create: (body: Pick<Contact, "name" | "email" | "phone" | "notes">) =>
      request("/contacts", contactSchema, json("POST", body)),
    update: (id: string, body: Partial<Pick<Contact, "name" | "email" | "phone" | "notes">>) =>
      request(`/contacts/${id}`, contactSchema, json("PATCH", body)),
    remove: (id: string) => request(`/contacts/${id}`, z.null(), json("DELETE")),
  },
  properties: {
    list: () => request("/properties", z.array(propertySchema)),
    get: (id: string) => request(`/properties/${id}`, propertySchema),
    create: (body: { display_name: string; address: string; attributes?: Record<string, unknown> }) =>
      request("/properties", propertySchema, json("POST", body)),
    update: (id: string, body: Partial<{ display_name: string; address: string; attributes: Record<string, unknown> }>) =>
      request(`/properties/${id}`, propertySchema, json("PATCH", body)),
    remove: (id: string) => request(`/properties/${id}`, z.null(), json("DELETE")),
  },
  showings: {
    list: (filters: ShowingFilters = {}) => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.dateFrom) params.set("date_from", filters.dateFrom);
      if (filters.dateTo) params.set("date_to", filters.dateTo);
      if (filters.contactId) params.set("contact_id", filters.contactId);
      if (filters.subjectId) params.set("subject_id", filters.subjectId);
      if (filters.unassigned !== undefined) params.set("unassigned", String(filters.unassigned));
      if (filters.query) params.set("q", filters.query);
      if (filters.cursor) params.set("cursor", filters.cursor);
      params.set("limit", String(filters.limit ?? 100));
      return request(`/showings?${params}`, showingListSchema);
    },
    listAll: (filters: ShowingFilters = {}) => listAllShowings(filters),
    get: (id: string) => request(`/showings/${id}`, showingDetailSchema),
    create: (body: { subject_id?: string; address?: string; contact_id?: string | null; consent_ack: boolean; consent_text_version?: string }) =>
      // The report prints the tour date, so it must be the browser's calendar
      // date rather than the server's UTC one.
      request("/showings", showingSchema, json("POST", { ...body, capture_timezone: browserTimezone() })),
    attachProperty: (id: string, body: { subject_id: string } | { address: string }) =>
      request(`/showings/${id}`, showingSchema, json("PATCH", body)),
    finish: (id: string) => request(`/showings/${id}/finish`, z.unknown(), json("POST")),
    reprocess: (id: string) => request(`/showings/${id}/reprocess`, z.unknown(), json("POST")),
    presign: (id: string, body: { type: string; content_type: string; timestamp_offset_ms?: number }) =>
      request(
        `/showings/${id}/media/presign`,
        z.object({
          media_id: z.string().uuid(),
          upload_url: z.string(),
          method: z.literal("PUT"),
          headers: z.record(z.string(), z.string()),
          expires_in: z.number(),
          max_size_bytes: z.number(),
        }),
        json("POST", body),
      ),
    complete: (visitId: string, mediaId: string) =>
      request(`/showings/${visitId}/media/${mediaId}/complete`, mediaSchema, json("POST")),
    mediaDownload: (visitId: string, mediaId: string) =>
      request(
        `/showings/${visitId}/media/${mediaId}/download`,
        z.object({ download_url: z.string(), expires_in: z.number() }),
      ),
    confirm: (id: string) =>
      request(
        `/showings/${id}/confirm`,
        z.object({
          visit_id: z.string().uuid(),
          report_id: z.string().uuid(),
          visit_status: z.string(),
          report_status: z.string(),
        }),
        json("POST"),
      ),
    createShareLink: (id: string) =>
      request(
        `/showings/${id}/share-links`,
        z.object({
          id: z.string().uuid(),
          token: z.string(),
          url: z.string(),
          expires_at: nullableString,
          revoked_at: nullableString,
        }),
        json("POST", {}),
      ),
    send: (id: string, body: { channel: "email" | "link_only"; to_email?: string }) =>
      request(
        `/showings/${id}/send`,
        z.object({
          send_id: z.string().uuid(),
          visit_status: z.string(),
          channel: z.string(),
          share_url: z.string(),
          to_email: nullableString,
        }),
        json("POST", body),
      ),
    revokeShareLink: (visitId: string, linkId: string) =>
      request(
        `/showings/${visitId}/share-links/${linkId}/revoke`,
        z.object({
          id: z.string().uuid(),
          token: z.string(),
          url: z.string(),
          expires_at: nullableString,
          revoked_at: dateString,
        }),
        json("POST"),
      ),
    delivery: (id: string) => request(`/showings/${id}/delivery`, deliverySchema),
  },
  observations: {
    update: (id: string, body: Partial<{ content: string; category: string; zone_id: string | null }>) =>
      request(`/observations/${id}`, observationSchema, json("PATCH", body)),
    confirm: (id: string) => request(`/observations/${id}/confirm`, observationSchema, json("POST")),
    dismiss: (id: string) => request(`/observations/${id}/dismiss`, observationSchema, json("POST")),
    create: (body: { visit_id: string; content: string; category: string; zone_id: string | null; source_transcript_segment_id?: string | null }) =>
      request("/observations", observationSchema, json("POST", body)),
  },
  transcript: {
    update: (id: string, text: string) =>
      request(`/transcript-segments/${id}`, transcriptSchema, json("PATCH", { text })),
  },
  reports: {
    update: (id: string, content: ReportContent) =>
      request(`/reports/${id}`, reportSchema, json("PATCH", { content })),
  },
  branding: {
    get: () => request("/branding", brandingSchema),
    update: (body: Omit<Branding, "id" | "logo_key" | "updated_at">) =>
      request("/branding", brandingSchema, json("PUT", body)),
    presignLogo: (contentType: string) =>
      request(
        "/branding/logo/presign",
        z.object({
          logo_key: z.string(),
          upload_url: z.string(),
          method: z.literal("PUT"),
          headers: z.record(z.string(), z.string()),
          expires_in: z.number(),
        }),
        json("POST", { content_type: contentType }),
      ),
    preview: () => requestText("/branding/preview"),
  },
  vertical: () => request("/vertical-config", verticalConfigSchema),
};

export async function listAllShowings(filters: ShowingFilters = {}): Promise<ShowingList> {
  const baseFilters = { ...filters };
  let cursor = baseFilters.cursor;
  delete baseFilters.cursor;
  delete baseFilters.limit;

  const seenCursors = new Set<string>();
  const items: Showing[] = [];
  while (true) {
    if (cursor !== undefined) {
      if (seenCursors.has(cursor)) {
        throw new Error(`Repeated showing pagination cursor: ${cursor}`);
      }
      seenCursors.add(cursor);
    }

    const page = await api.showings.list({ ...baseFilters, cursor, limit: 100 });
    items.push(...page.items);
    if (!page.next_cursor) break;
    cursor = page.next_cursor;
  }

  return { items: dedupeShowingsById(items), next_cursor: null };
}

export function uploadWithProgress(
  url: string,
  file: File,
  headers: Record<string, string>,
  onProgress: (percent: number) => void,
) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Upload failed (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(file);
  });
}
