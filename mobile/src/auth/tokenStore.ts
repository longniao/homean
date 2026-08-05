import * as SecureStore from 'expo-secure-store';
import type { TokenPair } from '../types';

const KEY = 'kawu.auth.tokens.v1';

export async function getTokens(): Promise<TokenPair | null> {
  const value = await SecureStore.getItemAsync(KEY);
  if (!value) return null;
  try { return JSON.parse(value) as TokenPair; } catch { return null; }
}

export async function setTokens(tokens: TokenPair): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(tokens), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
