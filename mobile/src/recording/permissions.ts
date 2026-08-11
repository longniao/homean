import { Platform } from 'react-native';

export type CapturePermissionFailure = 'microphone' | 'notifications';

export type CapturePermissionResult =
  | { granted: true }
  | { granted: false; failure: CapturePermissionFailure };

/**
 * Android 13 (API 33) introduced runtime notification permission. The
 * expo-audio background recording service needs it before the recorder is
 * prepared so the foreground-service notification can be shown.
 */
export function requiresAndroidNotificationPermission(
  platformOS: string = Platform.OS,
  platformVersion: string | number = Platform.Version,
): boolean {
  return platformOS === 'android' && Number(platformVersion) >= 33;
}

type PermissionResponse = { granted: boolean };

export async function requestCapturePermissions(options: {
  platformOS: string;
  platformVersion: string | number;
  requestRecording: () => Promise<PermissionResponse>;
  requestNotifications: () => Promise<PermissionResponse>;
}): Promise<CapturePermissionResult> {
  const microphone = await options.requestRecording();
  if (!microphone.granted) return { granted: false, failure: 'microphone' };

  if (!requiresAndroidNotificationPermission(options.platformOS, options.platformVersion)) return { granted: true };

  // This call is deliberately gated above: expo-audio throws on iOS and on
  // Android versions where this permission does not exist.
  const notifications = await options.requestNotifications();
  if (!notifications.granted) return { granted: false, failure: 'notifications' };
  return { granted: true };
}
