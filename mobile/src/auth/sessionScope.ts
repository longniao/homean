import type { Account } from '../types';

let account: Account | null = null;
let generation = 0;

export function activateSessionAccount(value: Account): void {
  account = value;
  generation += 1;
}
export function deactivateSessionAccount(): void {
  account = null;
  generation += 1;
}
export function sessionGeneration(): number { return generation; }
export function assertSessionGeneration(expected: number): void {
  if (expected !== generation) throw new Error('Account session changed');
}
export function currentSessionAccount(): Account {
  if (!account) throw new Error('An identified account is required for local capture');
  return account;
}
