import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { colors } from '../theme';

const VISIBLE_MS = 1_400;
const FADE_MS = 160;

export type ToastController = { message: string | null; show: (message: string) => void };

// A one-line confirmation that fades in, stays briefly, and fades out on its own.
// Successful captures use this instead of a modal so the agent never has to tap
// to dismiss feedback while talking to a client.
export function useToast(): ToastController {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const show = useCallback((next: string) => {
    if (timer.current) clearTimeout(timer.current);
    setMessage(next);
    timer.current = setTimeout(() => { setMessage(null); timer.current = null; }, VISIBLE_MS);
  }, []);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  return { message, show };
}

export function Toast({ message }: { message: string | null }) {
  const [opacity] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!message) return;
    opacity.setValue(0);
    Animated.timing(opacity, { toValue: 1, duration: FADE_MS, useNativeDriver: true }).start();
  }, [message, opacity]);
  if (!message) return null;
  return <Animated.View pointerEvents="none" accessibilityLiveRegion="polite" testID="toast" style={[styles.toast, { opacity }]}>
    <Text style={styles.text}>{message}</Text>
  </Animated.View>;
}

const styles = StyleSheet.create({
  toast: { position: 'absolute', left: 22, right: 22, bottom: 36, backgroundColor: colors.ink, borderRadius: 14, paddingVertical: 12, paddingHorizontal: 16, alignItems: 'center' },
  text: { color: colors.white, fontWeight: '600' },
});
