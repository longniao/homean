import '../../i18n';
import { Alert } from 'react-native';
import { fireEvent, render } from '@testing-library/react-native';
import { HomeScreen } from '../HomeScreen';
import type { LocalShowing } from '../../types';

describe('HomeScreen recording consent', () => {
  test('requires consent before starting and passes the acknowledgement', async () => {
    const onStart = jest.fn();
    const screen = await render(
      <HomeScreen
        account={null}
        consent={null}
        contacts={[]}
        onLogout={() => undefined}
        onOpenReport={() => undefined}
        onRefresh={() => undefined}
        onStart={onStart}
        properties={[]}
        refreshing={false}
        showings={[]}
      />,
    );

    await fireEvent.press(screen.getByRole('button', { name: 'Start Showing' }));
    const begin = screen.getByRole('button', { name: 'Begin recording' });
    expect(begin.props.accessibilityState?.disabled).toBe(true);

    await fireEvent.press(screen.getByRole('checkbox'));
    await fireEvent.press(screen.getByRole('button', { name: 'Begin recording' }));

    expect(onStart).toHaveBeenCalledWith({
      address: null,
      consentAck: true,
      // No cached policy in this test, so the wording the agent saw is the
      // bundled fallback and its version is recorded as unknown.
      consentTextVersion: null,
      contactId: null,
      subjectId: null,
      title: 'Untitled showing',
    });
  });
});

const account = {
  userId: 'user-1', email: 'agent@example.com', name: null,
  workspaceId: 'workspace-1', workspaceName: "agent's Workspace", role: 'buyers_agent',
};

function showing(overrides: Partial<LocalShowing>): LocalShowing {
  return {
    id: 'showing-1', remoteId: null, contactId: null, subjectId: null, address: null,
    title: '123 Main Street', startedAt: 1_760_000_000_000, endedAt: null, elapsedMs: 0,
    syncState: 'synced', processingStatus: null, finishRequested: false, lastError: null,
    updatedAt: 1_760_000_000_000, generation: 0, ...overrides,
  };
}

function renderHome(props: Partial<React.ComponentProps<typeof HomeScreen>> = {}) {
  return render(
    <HomeScreen
      account={null}
      consent={null}
      contacts={[]}
      onLogout={() => undefined}
      onOpenReport={() => undefined}
      onRefresh={() => undefined}
      onStart={() => undefined}
      properties={[]}
      refreshing={false}
      showings={[]}
      {...props}
    />,
  );
}

describe('HomeScreen signed-in identity', () => {
  test('shows the persisted account so a cold start names who is signed in', async () => {
    const screen = await renderHome({ account });
    expect(screen.getByText('Signed in as agent@example.com')).toBeTruthy();
  });

  test('prefers the display name once the profile has one', async () => {
    const screen = await renderHome({ account: { ...account, name: 'Dana Agent' } });
    expect(screen.getByText('Signed in as Dana Agent')).toBeTruthy();
  });

  test('says nothing before the first sign-in', async () => {
    const screen = await renderHome();
    expect(screen.queryByText(/Signed in as/)).toBeNull();
  });
});

describe('HomeScreen sign-out guard', () => {
  afterEach(() => { jest.restoreAllMocks(); });

  test('signs out immediately when everything has synced', async () => {
    const onLogout = jest.fn();
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = await renderHome({ onLogout, showings: [showing({ syncState: 'ready' })] });

    await fireEvent.press(screen.getByText('Sign out'));

    expect(alert).not.toHaveBeenCalled();
    expect(onLogout).toHaveBeenCalled();
  });

  test('warns before signing out while captures are still queued', async () => {
    const onLogout = jest.fn();
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = await renderHome({
      onLogout,
      showings: [showing({ syncState: 'local' }), showing({ id: 'showing-2', syncState: 'failed' })],
    });

    await fireEvent.press(screen.getByText('Sign out'));

    expect(onLogout).not.toHaveBeenCalled();
    expect(alert).toHaveBeenCalledWith(
      'Sign out',
      expect.stringContaining('2 showings have not synced yet'),
      expect.any(Array),
    );

    // Confirming from the dialog still signs out; the captures stay on device.
    const actions = alert.mock.calls[0]![2] as { text: string; onPress?: () => void }[];
    actions.find((action) => action.text === 'Sign out')?.onPress?.();
    expect(onLogout).toHaveBeenCalled();
  });
});
