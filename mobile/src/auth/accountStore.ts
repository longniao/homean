import * as SecureStore from 'expo-secure-store';
import type { Account } from '../types';

const KEY = 'homean.auth.account.v1';

/**
 * The signed-in identity is persisted alongside the tokens so a cold start —
 * including an offline one — can show who is signed in without a round trip.
 * It holds no credential; the tokens remain the only thing that grants access.
 */
export async function getAccount(): Promise<Account | null> {
  const value = await SecureStore.getItemAsync(KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as Account;
  } catch {
    return null;
  }
}

export async function setAccount(account: Account): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY, JSON.stringify(account), {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
  } catch {
    // The identity is a display convenience. Losing the write must never
    // interrupt a sign-in or a sync; the next refresh rewrites it.
  }
}

export async function clearAccount(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY).catch(() => undefined);
}
