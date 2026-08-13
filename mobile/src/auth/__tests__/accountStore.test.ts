import * as SecureStore from 'expo-secure-store';

import { clearAccount, getAccount, setAccount } from '../accountStore';

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

const account = {
  userId: 'user-1',
  email: 'agent@example.com',
  name: 'Dana Agent',
  workspaceId: 'workspace-1',
  workspaceName: "agent's Workspace",
  role: 'buyers_agent',
};

beforeEach(() => {
  jest.clearAllMocks();
  secureStore.getItemAsync.mockResolvedValue(null);
  secureStore.setItemAsync.mockResolvedValue(undefined);
  secureStore.deleteItemAsync.mockResolvedValue(undefined);
});

describe('persisted account identity', () => {
  test('round-trips the signed-in account', async () => {
    await setAccount(account);
    expect(secureStore.setItemAsync).toHaveBeenCalledWith(
      'homean.auth.account.v1',
      JSON.stringify(account),
      { keychainAccessible: 'when-unlocked' },
    );

    secureStore.getItemAsync.mockResolvedValue(JSON.stringify(account));
    await expect(getAccount()).resolves.toEqual(account);
  });

  test('reports no account before the first sign-in', async () => {
    await expect(getAccount()).resolves.toBeNull();
  });

  test('treats a corrupted record as no account rather than throwing', async () => {
    secureStore.getItemAsync.mockResolvedValue('not-json');
    await expect(getAccount()).resolves.toBeNull();
  });

  test('never fails a sign-in when the keychain write fails', async () => {
    secureStore.setItemAsync.mockRejectedValueOnce(new Error('keychain unavailable'));
    await expect(setAccount(account)).resolves.toBeUndefined();
  });

  test('clears the account on sign-out', async () => {
    await clearAccount();
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith('homean.auth.account.v1');
  });
});
