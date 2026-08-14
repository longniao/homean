import { ApiClient } from '../client';
import { clearTokens, getTokens } from '../../auth/tokenStore';

jest.mock('../../auth/tokenStore', () => ({
  clearTokens: jest.fn(),
  getTokens: jest.fn(async () => ({ accessToken: 'access-token', refreshToken: 'refresh-token', expiresAt: Date.now() + 60_000 })),
  setTokens: jest.fn(),
}));
jest.mock('../../auth/accountStore', () => ({
  clearAccount: jest.fn(),
  getAccount: jest.fn(async () => null),
  setAccount: jest.fn(),
}));

const tokenStore = { clearTokens: clearTokens as jest.Mock, getTokens: getTokens as jest.Mock };

/** Force the next request through the refresh path by expiring the access token. */
function expiredAccessToken(): void {
  tokenStore.getTokens.mockResolvedValue({ accessToken: 'stale', refreshToken: 'refresh-token', expiresAt: Date.now() - 1_000 });
}

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
      // An API that predates versioned consent parses to a null policy rather
      // than failing, so the client falls back to its bundled wording.
      consent: null,
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

describe('ApiClient session durability', () => {
  afterEach(() => {
    jest.restoreAllMocks();
    tokenStore.clearTokens.mockClear();
    tokenStore.getTokens.mockResolvedValue({ accessToken: 'access-token', refreshToken: 'refresh-token', expiresAt: Date.now() + 60_000 });
  });

  test.each([
    ['a rate limit', 429],
    ['a server error', 500],
    ['a bad gateway', 502],
    ['an unavailable backend', 503],
  ])('keeps the stored session when refresh fails with %s', async (_label, status) => {
    expiredAccessToken();
    jest.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status, json: async () => ({ detail: 'Too many requests' }),
    } as Response);
    const client = new ApiClient();
    const expired = jest.fn();
    client.onSessionExpired(expired);

    await expect(client.listShowings()).rejects.toMatchObject({ status });
    expect(tokenStore.clearTokens).not.toHaveBeenCalled();
    expect(expired).not.toHaveBeenCalled();
  });

  test.each([
    ['rejected', 401],
    ['forbidden', 403],
  ])('ends the session when the refresh token is %s', async (_label, status) => {
    expiredAccessToken();
    jest.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false, status, json: async () => ({ detail: 'Invalid token' }),
    } as Response);
    const client = new ApiClient();
    const expired = jest.fn();
    client.onSessionExpired(expired);

    await expect(client.listShowings()).rejects.toMatchObject({ status });
    expect(tokenStore.clearTokens).toHaveBeenCalled();
    expect(expired).toHaveBeenCalledTimes(1);
  });

  test('keeps the stored session when the device is offline', async () => {
    expiredAccessToken();
    jest.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Network request failed'));
    const client = new ApiClient();
    const expired = jest.fn();
    client.onSessionExpired(expired);

    await expect(client.listShowings()).rejects.toThrow('Network request failed');
    expect(tokenStore.clearTokens).not.toHaveBeenCalled();
    expect(expired).not.toHaveBeenCalled();
  });
});
