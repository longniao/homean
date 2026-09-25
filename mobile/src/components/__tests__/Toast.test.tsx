import { act, fireEvent, render } from '@testing-library/react-native';
import { Pressable, Text } from 'react-native';
import { Toast, useToast } from '../Toast';

function Harness() {
  const toast = useToast();
  return <><Pressable accessibilityRole="button" onPress={() => toast.show('Voice tag saved')}><Text>tag</Text></Pressable><Toast message={toast.message} /></>;
}

describe('Toast', () => {
  beforeEach(() => { jest.useFakeTimers(); });
  afterEach(() => { jest.useRealTimers(); });

  test('shows the message without blocking and hides itself', async () => {
    const screen = await render(<Harness />);
    expect(screen.queryByTestId('toast')).toBeNull();
    await fireEvent.press(screen.getByRole('button'));
    expect(screen.getByTestId('toast').props.pointerEvents).toBe('none');
    expect(screen.getByText('Voice tag saved')).toBeTruthy();
    await act(async () => { jest.advanceTimersByTime(2_000); });
    expect(screen.queryByTestId('toast')).toBeNull();
  });

  test('a second capture restarts the timer instead of stacking alerts', async () => {
    const screen = await render(<Harness />);
    await fireEvent.press(screen.getByRole('button'));
    await act(async () => { jest.advanceTimersByTime(1_000); });
    await fireEvent.press(screen.getByRole('button'));
    await act(async () => { jest.advanceTimersByTime(1_000); });
    expect(screen.getByText('Voice tag saved')).toBeTruthy();
    await act(async () => { jest.advanceTimersByTime(1_000); });
    expect(screen.queryByTestId('toast')).toBeNull();
  });
});
