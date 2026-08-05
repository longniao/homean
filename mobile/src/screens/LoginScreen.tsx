import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import { PrimaryButton } from '../components/ui';
import { colors } from '../theme';

export function LoginScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t } = useTranslation(); const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false); const [error, setError] = useState(false);
  const submit = async () => { setLoading(true); setError(false); try { await api.login(email.trim(), password); onAuthenticated(); } catch { setError(true); } finally { setLoading(false); } };
  return <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.page}>
    <View style={styles.mark}><Text style={styles.markText}>K</Text></View>
    <Text style={styles.title}>{t('auth.title')}</Text><Text style={styles.subtitle}>{t('auth.subtitle')}</Text>
    <Text style={styles.label}>{t('auth.email')}</Text><TextInput autoCapitalize="none" autoComplete="email" keyboardType="email-address" value={email} onChangeText={setEmail} style={styles.input} />
    <Text style={styles.label}>{t('auth.password')}</Text><TextInput secureTextEntry autoComplete="current-password" value={password} onChangeText={setPassword} style={styles.input} />
    {error && <Text style={styles.error}>{t('auth.invalid')}</Text>}
    <PrimaryButton label={t('auth.login')} loading={loading} disabled={!email || password.length < 8} onPress={() => { void submit(); }} style={styles.button} />
  </KeyboardAvoidingView>;
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream, justifyContent: 'center', padding: 28 }, mark: { width: 54, height: 54, borderRadius: 16, backgroundColor: colors.green, alignItems: 'center', justifyContent: 'center', marginBottom: 28 },
  markText: { color: colors.white, fontSize: 30, fontWeight: '800' }, title: { fontSize: 32, fontWeight: '800', color: colors.ink }, subtitle: { color: colors.muted, fontSize: 17, marginTop: 8, marginBottom: 30 },
  label: { color: colors.ink, fontWeight: '600', marginBottom: 8 }, input: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 15, fontSize: 16, marginBottom: 18 },
  error: { color: colors.red, marginBottom: 12 }, button: { marginTop: 6 },
});
