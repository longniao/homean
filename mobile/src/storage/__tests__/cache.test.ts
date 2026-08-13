import { captureRepository } from '../database';
import {
  clearCache, readDirectory, readShowingDetail, readVerticalConfig,
  writeDirectory, writeShowingDetail, writeVerticalConfig,
} from '../cache';
import type { ShowingDetail } from '../../types';

jest.mock('../database', () => ({
  captureRepository: { readCache: jest.fn(), writeCache: jest.fn(), clearCache: jest.fn() },
}));

const repository = captureRepository as unknown as {
  readCache: jest.Mock; writeCache: jest.Mock; clearCache: jest.Mock;
};

const directory = {
  contacts: [{ id: 'contact-1', name: 'Dana Buyer', email: 'dana@example.com' }],
  properties: [{ id: 'subject-1', displayName: '123 Main Street', address: '123 Main Street' }],
};

const detail: ShowingDetail = {
  id: 'visit-1', status: 'draft', processingStatus: 'ready', createdAt: '2026-08-10T00:00:00Z', consentAck: true,
  property: { id: 'subject-1', displayName: '123 Main Street', address: '123 Main Street' }, contact: null,
  observations: [{
    id: 'observation-1', zoneId: 'zone-1', category: 'concern', content: 'The street is busy.',
    sourceTranscriptSegmentId: null, timestampStart: null, flags: { sensitive: false }, reviewStatus: 'confirmed',
  }],
  report: {
    id: 'report-1', status: 'draft', content: {
      executive_summary: 'A concise summary.',
      room_by_room: [{ zone_id: 'zone-1', zone_type: 'primary_bedroom', bullets: [{ text: 'Good light.', observation_ids: [] }] }],
      highlights: [], concerns: [], follow_ups: [],
    },
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  repository.readCache.mockResolvedValue(null);
  repository.writeCache.mockResolvedValue(undefined);
  repository.clearCache.mockResolvedValue(undefined);
});

describe('offline reference cache', () => {
  test('round-trips the client and property directory', async () => {
    await writeDirectory(directory);
    expect(repository.writeCache).toHaveBeenCalledWith('directory.v1', directory);

    repository.readCache.mockResolvedValue(directory);
    await expect(readDirectory()).resolves.toEqual(directory);
  });

  test('round-trips a showing detail under its own key', async () => {
    await writeShowingDetail(detail);
    expect(repository.writeCache).toHaveBeenCalledWith('showing_detail.v1:visit-1', detail);

    repository.readCache.mockResolvedValue(detail);
    await expect(readShowingDetail('visit-1')).resolves.toEqual(detail);
  });

  test('round-trips the vertical config', async () => {
    const config = {
      zoneTaxonomy: ['primary_bedroom'], observationSchema: ['concern'],
      displayLabels: { zones: { primary_bedroom: 'Primary bedroom' }, observations: { concern: 'Buyer concern' } },
    };
    await writeVerticalConfig(config);
    repository.readCache.mockResolvedValue(config);
    await expect(readVerticalConfig()).resolves.toEqual(config);
  });

  test('reports a miss rather than returning a record an older build wrote', async () => {
    repository.readCache.mockResolvedValue({ contacts: [{ id: 'contact-1' }], properties: [] });
    await expect(readDirectory()).resolves.toBeNull();
  });

  test('reports a miss when the store itself is unreadable', async () => {
    repository.readCache.mockRejectedValue(new Error('database is locked'));
    await expect(readDirectory()).resolves.toBeNull();
    await expect(readShowingDetail('visit-1')).resolves.toBeNull();
    await expect(readVerticalConfig()).resolves.toBeNull();
  });

  test('never propagates a write failure to the caller that produced the data', async () => {
    repository.writeCache.mockRejectedValue(new Error('disk full'));
    await expect(writeDirectory(directory)).resolves.toBeUndefined();
    await expect(writeShowingDetail(detail)).resolves.toBeUndefined();
  });

  test('drops everything on sign-out', async () => {
    await clearCache();
    expect(repository.clearCache).toHaveBeenCalled();
  });
});
