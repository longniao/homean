import '../../i18n';
import { fireEvent, render } from '@testing-library/react-native';
import { HomeScreen } from '../HomeScreen';

describe('HomeScreen recording consent', () => {
  test('requires consent before starting and passes the acknowledgement', async () => {
    const onStart = jest.fn();
    const screen = await render(
      <HomeScreen
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
      contactId: null,
      subjectId: null,
      title: 'Untitled showing',
    });
  });
});
