import { z } from 'zod';
import { captureRepository } from './database';
import type { Contact, Property, ShowingDetail, VerticalConfig } from '../types';

/**
 * Server-owned reference data mirrored on the device so an offline cold start
 * is not a blank app. Every read is schema-validated: a cache written by an
 * older build must degrade to "no cache" rather than crash a screen.
 */
const contactSchema = z.object({ id: z.string(), name: z.string(), email: z.string().nullable() });
const propertySchema = z.object({ id: z.string(), displayName: z.string(), address: z.string() });
const directorySchema = z.object({
  contacts: z.array(contactSchema),
  properties: z.array(propertySchema),
});
const verticalConfigSchema = z.object({
  zoneTaxonomy: z.array(z.string()),
  observationSchema: z.array(z.string()),
  displayLabels: z.object({
    zones: z.record(z.string(), z.string()),
    observations: z.record(z.string(), z.string()),
  }),
  // Cached so an offline showing can still display the authoritative consent
  // wording rather than falling back to the bundled copy.
  consent: z.object({ version: z.string(), text: z.string() }).nullable().catch(null),
});
const bulletSchema = z.object({ text: z.string(), observation_ids: z.array(z.string()) });
const showingDetailSchema = z.object({
  id: z.string(), status: z.string(), processingStatus: z.string(), createdAt: z.string(),
  consentAck: z.boolean().optional(),
  property: propertySchema.nullable(), contact: contactSchema.nullable(),
  observations: z.array(z.object({
    id: z.string(), zoneId: z.string().nullable(), category: z.string(), content: z.string(),
    sourceTranscriptSegmentId: z.string().nullable(), timestampStart: z.number().nullable(),
    flags: z.object({
      sensitive: z.boolean().optional(),
      reason: z.string().nullable().optional(),
      suggested_rewrite: z.string().nullable().optional(),
    }),
    reviewStatus: z.string(),
  })),
  report: z.object({
    id: z.string(), status: z.string(),
    content: z.object({
      executive_summary: z.string(),
      room_by_room: z.array(z.object({ zone_id: z.string().nullable(), zone_type: z.string().nullable(), bullets: z.array(bulletSchema) })),
      highlights: z.array(bulletSchema), concerns: z.array(bulletSchema), follow_ups: z.array(bulletSchema),
    }),
  }).nullable(),
});

const DIRECTORY_KEY = 'directory.v1';
const VERTICAL_CONFIG_KEY = 'vertical_config.v1';
const showingDetailKey = (visitId: string) => `showing_detail.v1:${visitId}`;

/**
 * Every cache operation is best-effort. A cache miss and an unreadable store
 * must be indistinguishable to callers: this is an optimization, and a screen
 * that awaits it can never be left hanging by a storage failure.
 */
async function read<T>(key: string, schema: z.ZodType<T>): Promise<T | null> {
  try {
    const parsed = schema.safeParse(await captureRepository.readCache(key));
    return parsed.success ? parsed.data : null;
  } catch { return null; }
}

async function write(key: string, value: unknown): Promise<void> {
  try { await captureRepository.writeCache(key, value); } catch { /* the next success rewrites it */ }
}

export interface Directory { contacts: Contact[]; properties: Property[] }

export function readDirectory(): Promise<Directory | null> {
  return read(DIRECTORY_KEY, directorySchema);
}
export function writeDirectory(directory: Directory): Promise<void> {
  return write(DIRECTORY_KEY, directory);
}

export function readVerticalConfig(): Promise<VerticalConfig | null> {
  return read(VERTICAL_CONFIG_KEY, verticalConfigSchema);
}
export function writeVerticalConfig(config: VerticalConfig): Promise<void> {
  return write(VERTICAL_CONFIG_KEY, config);
}

export function readShowingDetail(visitId: string): Promise<ShowingDetail | null> {
  return read(showingDetailKey(visitId), showingDetailSchema) as Promise<ShowingDetail | null>;
}
export function writeShowingDetail(detail: ShowingDetail): Promise<void> {
  return write(showingDetailKey(detail.id), detail);
}

/**
 * Called on sign-out. Reference data belongs to the account that fetched it and
 * must not leak into the next session on a shared device.
 */
export async function clearCache(): Promise<void> {
  try { await captureRepository.clearCache(); } catch { /* nothing here outlives a reinstall anyway */ }
}
