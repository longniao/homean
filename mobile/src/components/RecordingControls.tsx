import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import type { RecordingState } from '../recording/machine';
import { formatElapsed } from '../recording/machine';
import { colors } from '../theme';

interface Props {
  state: RecordingState; onResume: () => void; onPhoto: () => void; onVideo: () => void; onVoiceTag: () => void; onEnd: () => void;
  resumeDisabled?: boolean;
}

export function RecordingControls({ state, onResume, onPhoto, onVideo, onVoiceTag, onEnd, resumeDisabled = false }: Props) {
  const { t } = useTranslation();
  const interrupted = state.phase === 'interrupted' || state.phase === 'error';
  return (
    <View style={styles.wrap}>
      <View style={styles.pulse} accessibilityLabel={interrupted ? t('recording.interrupted') : t('recording.recording')} />
      <Text style={styles.status}>{interrupted ? t('recording.interrupted') : t('recording.recording')}</Text>
      <Text style={styles.timer} testID="elapsed-time">{formatElapsed(state.elapsedMs)}</Text>
      {interrupted ? (
        <Pressable accessibilityRole="button" accessibilityState={{ disabled: resumeDisabled }} style={[styles.resume, resumeDisabled && styles.disabled]} onPress={onResume} disabled={resumeDisabled}><Text style={styles.resumeText}>{t('recording.resume')}</Text></Pressable>
      ) : (
        <View style={styles.actions}>
          <Pressable accessibilityRole="button" accessibilityLabel={t('recording.photo')} style={styles.action} onPress={onPhoto}><Text style={styles.icon}>▣</Text><Text>{t('recording.photo')}</Text></Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel={t('recording.video')} style={styles.action} onPress={onVideo}><Text style={styles.icon}>●</Text><Text>{t('recording.video')}</Text></Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel={t('recording.voiceTag')} style={styles.tag} onPress={onVoiceTag}><Text style={styles.icon}>＋</Text><Text>{t('recording.voiceTag')}</Text></Pressable>
        </View>
      )}
      <Pressable accessibilityRole="button" style={styles.end} onPress={onEnd}><Text style={styles.endText}>{t('recording.end')}</Text></Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24 },
  pulse: { width: 18, height: 18, borderRadius: 9, backgroundColor: colors.red },
  status: { fontSize: 18, color: colors.muted }, timer: { fontSize: 64, fontWeight: '300', color: colors.ink, fontVariant: ['tabular-nums'] },
  actions: { flexDirection: 'row', gap: 8, marginTop: 24 },
  action: { width: 80, height: 80, borderRadius: 40, backgroundColor: colors.green, alignItems: 'center', justifyContent: 'center', gap: 4 },
  tag: { width: 80, height: 80, borderRadius: 40, backgroundColor: colors.greenSoft, alignItems: 'center', justifyContent: 'center', gap: 4 },
  icon: { fontSize: 22, color: colors.ink }, resume: { backgroundColor: colors.green, paddingHorizontal: 28, paddingVertical: 16, borderRadius: 28 },
  resumeText: { color: colors.white, fontWeight: '700' }, disabled: { opacity: 0.45 }, end: { marginTop: 38, padding: 14 }, endText: { color: colors.red, fontSize: 18, fontWeight: '700' },
});
