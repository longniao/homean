import * as SecureStore from 'expo-secure-store';

import { clearTokens, getTokens, setTokens } from '../tokenStore';

jest.mock('expo-secure-store', () => ({
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: 'when-unlocked',
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

const secureStore = SecureStore as unknown as {
  getItemAsync: jest.Mock;
  setItemAsync: jest.Mock;
  deleteItemAsync: jest.Mock;
};

const tokens = {
  accessToken: 'access-token',
  refreshToken: 'refresh-token',
  expiresAt: 123,
};

beforeEach(() => {
  jest.clearAllMocks();
  secureStore.getItemAsync.mockResolvedValue(null);
  secureStore.setItemAsync.mockResolvedValue(undefined);
  secureStore.deleteItemAsync.mockResolvedValue(undefined);
});

describe('Homean token storage compatibility', () => {
  test('migrates a legacy Kawu token after writing the Homean key', async () => {
    secureStore.getItemAsync
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(JSON.stringify(tokens));

    await expect(getTokens()).resolves.toEqual(tokens);
    expect(secureStore.setItemAsync).toHaveBeenCalledWith(
      'homean.auth.tokens.v1',
      JSON.stringify(tokens),
      { keychainAccessible: 'when-unlocked' },
    );
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith('kawu.auth.tokens.v1');
  });

  test('writes Homean tokens and clears both namespaces on logout', async () => {
    await setTokens(tokens);
    expect(secureStore.setItemAsync).toHaveBeenCalledWith(
      'homean.auth.tokens.v1',
      JSON.stringify(tokens),
      { keychainAccessible: 'when-unlocked' },
    );
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith('kawu.auth.tokens.v1');

    await clearTokens();
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith('homean.auth.tokens.v1');
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith('kawu.auth.tokens.v1');
  });

  test('returns the legacy token if the replacement write fails', async () => {
    secureStore.getItemAsync
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(JSON.stringify(tokens));
    secureStore.setItemAsync.mockRejectedValueOnce(new Error('keychain unavailable'));

    await expect(getTokens()).resolves.toEqual(tokens);
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalled();
  });
});
