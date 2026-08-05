import type { PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, type TextStyle, View, type ViewStyle, type StyleProp } from 'react-native';
import { colors } from '../theme';

export function PrimaryButton({ label, onPress, disabled, loading, style }: { label: string; onPress: () => void; disabled?: boolean; loading?: boolean; style?: ViewStyle }) {
  return <Pressable accessibilityRole="button" disabled={disabled || loading} onPress={onPress} style={[styles.primary, (disabled || loading) && styles.disabled, style]}>{loading ? <ActivityIndicator color={colors.white} /> : <Text style={styles.primaryText}>{label}</Text>}</Pressable>;
}
export function SecondaryButton({ label, onPress, style, textStyle }: { label: string; onPress: () => void; style?: ViewStyle; textStyle?: TextStyle }) {
  return <Pressable accessibilityRole="button" onPress={onPress} style={[styles.secondary, style]}><Text style={[styles.secondaryText, textStyle]}>{label}</Text></Pressable>;
}
export function Card({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) { return <View style={[styles.card, style]}>{children}</View>; }

const styles = StyleSheet.create({
  primary: { backgroundColor: colors.green, minHeight: 54, borderRadius: 14, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20 },
  primaryText: { color: colors.white, fontSize: 17, fontWeight: '700' }, disabled: { opacity: 0.45 },
  secondary: { minHeight: 46, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  secondaryText: { color: colors.ink, fontWeight: '600' },
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 18, padding: 16 },
});
