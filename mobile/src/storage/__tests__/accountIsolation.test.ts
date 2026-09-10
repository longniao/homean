import { SyncEngine } from '../../sync/engine';
import * as SQLite from 'expo-sqlite';
import { activateSessionAccount, deactivateSessionAccount } from '../../auth/sessionScope';
import { accountDatabaseName, CAPTURE_DATABASE_NAME, captureRepository, repositoryForAccount } from '../database';
import type { Account } from '../../types';
jest.mock('expo-sqlite', () => ({ openDatabaseAsync: jest.fn() }));
const a: Account = { userId: '11111111-1111-4111-8111-111111111111', workspaceId: '22222222-2222-4222-8222-222222222222', email: 'a@example.com', name: null, workspaceName: 'A', role: 'buyers_agent' };
const b: Account = { ...a, userId: '33333333-3333-4333-8333-333333333333', workspaceId: '44444444-4444-4444-8444-444444444444' };

test('A → logout → B hides and does not sync A captures, while returning to A recovers them', async () => {
  const rows = new Map<string, Record<string, unknown>[]>();
  (SQLite.openDatabaseAsync as jest.Mock).mockImplementation(async (name: string) => {
    const entries: Record<string, unknown>[] = []; rows.set(name, entries);
    return {
      execAsync: async () => {},
      runAsync: async (sql: string, ...args: unknown[]) => {
        if (sql.startsWith('INSERT INTO local_showings')) entries.push({ id: args[0], contact_id: args[1], subject_id: args[2], address: args[3], title: args[4], started_at: args[5], sync_state: args[6], updated_at: args[7], generation: args[8], consent_ack: args[9], consent_text_version: args[10] });
        return { changes: 1 };
      },
      getFirstAsync: async (_sql: string, id: unknown) => entries.find((row) => row.id === id) ?? null,
      getAllAsync: async () => entries,
    };
  });
  activateSessionAccount(a);
  const boundToA = repositoryForAccount(a);
  const showing = await captureRepository.createShowing({ contactId: null, subjectId: null, address: null, title: 'Private A tour', consentAck: true });
  deactivateSessionAccount();
  expect(() => captureRepository.listShowings()).toThrow('identified account');
  activateSessionAccount(b);
  expect(await captureRepository.listShowings()).toEqual([]);
  expect(await captureRepository.pendingShowings()).toEqual([]);
  const transport = { createShowing: jest.fn(), presignMedia: jest.fn(), uploadFile: jest.fn(), completeMedia: jest.fn(), createMarker: jest.fn(), finishShowing: jest.fn() };
  await new SyncEngine(repositoryForAccount(b), transport, { isOnline: async () => true }).run();
  expect(transport.createShowing).not.toHaveBeenCalled();
  expect(transport.uploadFile).not.toHaveBeenCalled();
  expect(await captureRepository.getShowing(showing.id)).toBeNull();
  // Work already bound to A never mutates B's database after switching accounts.
  await boundToA.createShowing({ contactId: null, subjectId: null, address: null, title: 'A recovery' });
  expect(await captureRepository.listShowings()).toEqual([]);
  activateSessionAccount(a);
  expect((await captureRepository.pendingShowings()).map((item) => item.title)).toEqual(['Private A tour', 'A recovery']);
  expect(rows.has(CAPTURE_DATABASE_NAME)).toBe(false);
  expect(accountDatabaseName(a)).not.toBe(accountDatabaseName(b));
  deactivateSessionAccount();
});
