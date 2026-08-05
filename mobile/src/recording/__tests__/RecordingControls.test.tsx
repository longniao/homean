import '../../i18n';
import { fireEvent, render } from '@testing-library/react-native';
import { useReducer } from 'react';
import { Text } from 'react-native';
import { RecordingControls } from '../../components/RecordingControls';
import { initialRecordingState, recordingReducer } from '../machine';

function Harness({ recovered = false }: { recovered?: boolean }) {
  const [state, dispatch] = useReducer(recordingReducer, recovered ? { ...initialRecordingState, phase: 'interrupted', elapsedMs: 12_000 } : { ...initialRecordingState, phase: 'recording' });
  return <><Text testID="phase">{state.phase}</Text><RecordingControls state={state} onResume={() => dispatch({ type: 'RESUME' })} onPhoto={() => undefined} onVoiceTag={() => undefined} onEnd={() => dispatch({ type: 'STOP' })} /></>;
}

describe('RecordingControls state machine', () => {
  test('restored capture offers resume and transitions to preparing', async () => {
    const screen = await render(<Harness recovered />); expect(screen.getByTestId('elapsed-time').props.children).toBe('00:12');
    await fireEvent.press(screen.getByRole('button', { name: 'Resume recording' })); expect(screen.getByTestId('phase').props.children).toBe('preparing');
  });
  test('active capture exposes timestamp actions and transitions to stopping', async () => {
    const screen = await render(<Harness />); expect(screen.getByRole('button', { name: 'Photo' })).toBeTruthy(); expect(screen.getByRole('button', { name: 'Voice Tag' })).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'End' })); expect(screen.getByTestId('phase').props.children).toBe('stopping');
  });
});
