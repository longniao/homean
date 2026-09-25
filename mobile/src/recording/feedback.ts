import * as Haptics from 'expo-haptics';

// A short success buzz for a saved voice tag, photo or video. Haptics are
// best-effort: simulators and some Android devices have no engine, and a
// missing buzz must never turn into an error during a showing.
export async function captureFeedback(): Promise<void> {
  try { await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); } catch { /* no haptic engine */ }
}
