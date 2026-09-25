import { useState } from 'react';
import { KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { ApiError, api } from '../api/client';
import { Field, PrimaryButton } from '../components/ui';
import { colors } from '../theme';

type Mode = 'login' | 'signup';

export function LoginScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t } = useTranslation(); const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setLoading(true); setError(null);
    try { await (mode === 'login' ? api.login(email.trim(), password) : api.signup(email.trim(), password)); onAuthenticated(); }
    catch (caught) { setError(mode === 'signup' && caught instanceof ApiError && caught.status === 409 ? t('auth.emailTaken') : t('auth.invalid')); }
    finally { setLoading(false); }
  };
  const switchMode = () => { setMode(mode === 'login' ? 'signup' : 'login'); setError(null); };
  return <KeyboardAvoidingView behavior="padding" style={styles.page}>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
      <View style={styles.mark}><Text style={styles.markText}>H</Text></View>
      <Text style={styles.title}>{t('auth.title')}</Text><Text style={styles.subtitle}>{mode === 'login' ? t('auth.subtitle') : t('auth.signupSubtitle')}</Text>
      <Text style={styles.label}>{t('auth.email')}</Text><Field accessibilityLabel={t('auth.email')} autoCapitalize="none" autoComplete="email" keyboardType="email-address" textContentType="emailAddress" value={email} onChangeText={setEmail} style={styles.input} />
      <Text style={styles.label}>{t('auth.password')}</Text><Field accessibilityLabel={t('auth.password')} secureTextEntry autoComplete={mode === 'login' ? 'current-password' : 'new-password'} textContentType={mode === 'login' ? 'password' : 'newPassword'} placeholder={mode === 'signup' ? t('auth.passwordHint') : undefined} value={password} onChangeText={setPassword} style={styles.input} onSubmitEditing={() => { void submit(); }} />
      {error && <Text style={styles.error}>{error}</Text>}
      <PrimaryButton label={mode === 'login' ? t('auth.login') : t('auth.signup')} loading={loading} disabled={!email || password.length < 8} onPress={() => { void submit(); }} style={styles.button} />
      <Pressable accessibilityRole="button" onPress={switchMode} style={styles.switch}><Text style={styles.switchText}>{mode === 'login' ? t('auth.toSignup') : t('auth.toLogin')}</Text></Pressable>
    </ScrollView>
  </KeyboardAvoidingView>;
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream }, content: { flexGrow: 1, justifyContent: 'center', padding: 28, paddingBottom: 40 },
  mark: { width: 54, height: 54, borderRadius: 16, backgroundColor: colors.green, alignItems: 'center', justifyContent: 'center', marginBottom: 28 },
  markText: { color: colors.white, fontSize: 30, fontWeight: '800' }, title: { fontSize: 32, fontWeight: '800', color: colors.ink }, subtitle: { color: colors.muted, fontSize: 17, marginTop: 8, marginBottom: 30 },
  label: { color: colors.ink, fontWeight: '600', marginBottom: 8 }, input: { padding: 15, marginBottom: 18 },
  error: { color: colors.red, marginBottom: 12 }, button: { marginTop: 6 }, switch: { marginTop: 22, alignSelf: 'center', padding: 8 }, switchText: { color: colors.green, fontWeight: '600' },
});
