import * as SecureStore from 'expo-secure-store';
import type { TokenPair } from '../types';

const KEY = 'homean.auth.tokens.v1';
const LEGACY_KEY = 'kawu.auth.tokens.v1';

function parseTokens(value: string | null): TokenPair | null {
  if (!value) return null;
  try { return JSON.parse(value) as TokenPair; } catch { return null; }
}

export async function getTokens(): Promise<TokenPair | null> {
  const current = parseTokens(await SecureStore.getItemAsync(KEY));
  if (current) return current;

  const legacyValue = await SecureStore.getItemAsync(LEGACY_KEY);
  const legacy = parseTokens(legacyValue);
  if (!legacy) return null;

  // Write the replacement before deleting the old key. If a device-level
  // keychain write fails, returning the legacy value still preserves login.
  try {
    await SecureStore.setItemAsync(KEY, JSON.stringify(legacy), {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    await SecureStore.deleteItemAsync(LEGACY_KEY);
  } catch {
    // Keep reading the legacy value until the next successful migration.
  }
  return legacy;
}

export async function setTokens(tokens: TokenPair): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(tokens), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  try {
    await SecureStore.deleteItemAsync(LEGACY_KEY);
  } catch {
    // A successful Homean write is enough to preserve the session; the old
    // key is harmless and will be removed by a later clear/migration.
  }
}

export async function clearTokens(): Promise<void> {
  await Promise.allSettled([
    SecureStore.deleteItemAsync(KEY),
    SecureStore.deleteItemAsync(LEGACY_KEY),
  ]);
}
