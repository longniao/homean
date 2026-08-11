import { ApiClient } from '../client';

jest.mock('../../auth/tokenStore', () => ({
  clearTokens: jest.fn(),
  getTokens: jest.fn(async () => ({ accessToken: 'access-token', refreshToken: 'refresh-token', expiresAt: Date.now() + 60_000 })),
  setTokens: jest.fn(),
}));

describe('ApiClient vertical config', () => {
  test('requests and maps the config-driven display labels', async () => {
    const fetchMock = jest.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        zone_taxonomy: ['primary_bedroom'], observation_schema: ['concern'],
        display_labels: { zones: { primary_bedroom: 'Primary bedroom' }, observations: { concern: 'Buyer concern' } },
      }),
    } as Response);

    await expect(new ApiClient().getVerticalConfig()).resolves.toEqual({
      zoneTaxonomy: ['primary_bedroom'], observationSchema: ['concern'],
      displayLabels: { zones: { primary_bedroom: 'Primary bedroom' }, observations: { concern: 'Buyer concern' } },
    });
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/vertical-config', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer access-token' }),
    }));
    fetchMock.mockRestore();
  });

  test('sends the stable local media identity when presigning', async () => {
    const fetchMock = jest.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        media_id: 'remote-media-1',
        upload_url: 'https://upload/media-1',
        headers: { 'Content-Type': 'audio/mp4' },
        expires_at: '2026-08-10T12:15:00Z',
        expires_in: 900,
      }),
    } as Response);

    await new ApiClient().presignMedia('visit-1', {
      clientId: 'local-media-1',
      kind: 'audio',
      contentType: 'audio/mp4',
      timestampOffsetMs: 125,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/showings/visit-1/media/presign',
      expect.objectContaining({
        body: JSON.stringify({
          client_id: 'local-media-1',
          type: 'audio',
          content_type: 'audio/mp4',
          timestamp_offset_ms: 125,
        }),
      }),
    );
    fetchMock.mockRestore();
  });
});
