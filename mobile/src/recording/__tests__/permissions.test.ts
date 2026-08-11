import {
  requestCapturePermissions,
  requiresAndroidNotificationPermission,
} from '../permissions';

describe('recording permissions', () => {
  test('requires notifications only on Android 13 and later', () => {
    expect(requiresAndroidNotificationPermission('android', 32)).toBe(false);
    expect(requiresAndroidNotificationPermission('android', 33)).toBe(true);
    expect(requiresAndroidNotificationPermission('android', '35')).toBe(true);
    expect(requiresAndroidNotificationPermission('ios', 17)).toBe(false);
  });

  test('does not request notification permission on iOS or older Android', async () => {
    const requestNotifications = jest.fn(async () => ({ granted: false }));
    const requestRecording = jest.fn(async () => ({ granted: true }));

    await expect(requestCapturePermissions({
      platformOS: 'ios', platformVersion: 18, requestRecording, requestNotifications,
    })).resolves.toEqual({ granted: true });
    await expect(requestCapturePermissions({
      platformOS: 'android', platformVersion: 32, requestRecording, requestNotifications,
    })).resolves.toEqual({ granted: true });
    expect(requestNotifications).not.toHaveBeenCalled();
  });

  test('fails closed when Android notification access is denied', async () => {
    const requestNotifications = jest.fn(async () => ({ granted: false }));
    const result = await requestCapturePermissions({
      platformOS: 'android', platformVersion: 33,
      requestRecording: async () => ({ granted: true }), requestNotifications,
    });

    expect(result).toEqual({ granted: false, failure: 'notifications' });
    expect(requestNotifications).toHaveBeenCalledTimes(1);
  });

  test('does not request notifications when microphone access is denied', async () => {
    const requestNotifications = jest.fn(async () => ({ granted: true }));
    const result = await requestCapturePermissions({
      platformOS: 'android', platformVersion: 35,
      requestRecording: async () => ({ granted: false }), requestNotifications,
    });

    expect(result).toEqual({ granted: false, failure: 'microphone' });
    expect(requestNotifications).not.toHaveBeenCalled();
  });
});
