import * as Haptics from 'expo-haptics';
import { captureFeedback } from '../feedback';

jest.mock('expo-haptics', () => ({ notificationAsync: jest.fn(), NotificationFeedbackType: { Success: 'success' } }));

describe('captureFeedback', () => {
  test('plays a success buzz', async () => {
    await captureFeedback();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
  });
  test('never throws when the device has no haptic engine', async () => {
    (Haptics.notificationAsync as jest.Mock).mockRejectedValueOnce(new Error('unavailable'));
    await expect(captureFeedback()).resolves.toBeUndefined();
  });
});
