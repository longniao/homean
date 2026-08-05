import { useEffect, useReducer, useRef, useState } from 'react';
import { Alert, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Directory, File, Paths } from 'expo-file-system';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import { useTranslation } from 'react-i18next';
import { RecordingControls } from '../components/RecordingControls';
import { colors } from '../theme';
import { initialRecordingState, recordingReducer } from '../recording/machine';
import { captureRepository } from '../storage/database';
import type { LocalShowing } from '../types';

export function RecordingScreen({ showing, recovered, onFinished }: { showing: LocalShowing; recovered: boolean; onFinished: () => void }) {
  const { t } = useTranslation();
  const [state, dispatch] = useReducer(recordingReducer, recovered ? { ...initialRecordingState, phase: 'interrupted', elapsedMs: showing.elapsedMs, segmentStartedAtMs: showing.elapsedMs } : initialRecordingState);
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, directory: 'document' }, (status) => {
    if (status.hasError || status.mediaServicesDidReset) dispatch({ type: 'INTERRUPTED', error: status.error ?? undefined });
  });
  const recorderState = useAudioRecorderState(recorder, 500); const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions(); const camera = useRef<CameraView>(null); const starting = useRef(false);

  useEffect(() => {
    if (!recovered || state.phase !== 'interrupted') return;
    void (async () => {
      const session = await captureRepository.recordingSession(showing.id);
      if (session) {
        if (new File(session.fileUri).exists) await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'audio', fileUri: session.fileUri, contentType: 'audio/mp4', timestampOffsetMs: session.segmentOffsetMs });
        await captureRepository.clearRecordingSession(showing.id);
      }
    })();
  }, [recovered, showing.id, state.phase]);

  useEffect(() => {
    if (state.phase !== 'recording') return;
    const elapsed = state.segmentStartedAtMs + recorderState.durationMillis;
    dispatch({ type: 'TICK', elapsedMs: elapsed });
    void captureRepository.updateElapsed(showing.id, elapsed);
  }, [recorderState.durationMillis, showing.id, state.phase, state.segmentStartedAtMs]);

  async function startSegment() {
    if (starting.current) return; starting.current = true; dispatch({ type: state.phase === 'idle' ? 'START' : 'RESUME' });
    try {
      if (state.phase === 'interrupted' || state.phase === 'error') await closeSegment();
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) { Alert.alert(t('recording.permission')); dispatch({ type: 'FAIL', error: t('recording.permission') }); return; }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true, allowsBackgroundRecording: true, interruptionMode: 'doNotMix' });
      await recorder.prepareToRecordAsync();
      if (!recorder.uri) throw new Error(t('common.error'));
      await captureRepository.saveRecordingSession(showing.id, recorder.uri, state.elapsedMs);
      recorder.record(); dispatch({ type: 'READY', at: state.elapsedMs });
    } catch (error) { dispatch({ type: 'FAIL', error: error instanceof Error ? error.message : t('common.error') }); }
    finally { starting.current = false; }
  }

  useEffect(() => {
    if (!recovered && state.phase === 'idle') void startSegment();
    // The recorder is stable for the lifetime of this screen; start only on initial mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function closeSegment() {
    const offset = state.segmentStartedAtMs;
    try { if (recorder.isRecording) await recorder.stop(); } catch { /* preserve any file the recorder produced */ }
    if (recorder.uri && new File(recorder.uri).exists) await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'audio', fileUri: recorder.uri, contentType: 'audio/mp4', timestampOffsetMs: offset });
    await captureRepository.clearRecordingSession(showing.id);
  }

  const end = () => Alert.alert(t('recording.endTitle'), t('recording.endBody'), [
    { text: t('common.cancel'), style: 'cancel' },
    { text: t('recording.endConfirm'), style: 'destructive', onPress: () => { void (async () => { dispatch({ type: 'STOP' }); await closeSegment(); await captureRepository.finish(showing.id, state.elapsedMs); dispatch({ type: 'STOPPED' }); onFinished(); })(); } },
  ]);
  const tag = () => { void captureRepository.addVoiceTag(showing.id, state.elapsedMs); Alert.alert(t('recording.tagged')); };
  const openCamera = async () => { if (!cameraPermission?.granted && !(await requestCameraPermission()).granted) { Alert.alert(t('recording.cameraPermission')); return; } setCameraOpen(true); };
  const takePhoto = async () => {
    const result = await camera.current?.takePictureAsync({ quality: 0.85 }); if (!result) return;
    const directory = new Directory(Paths.document, 'showing-photos'); if (!directory.exists) directory.create({ idempotent: true, intermediates: true });
    const destination = new File(directory, `${showing.id}-${Date.now()}.jpg`); await new File(result.uri).copy(destination);
    await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'photo', fileUri: destination.uri, contentType: 'image/jpeg', timestampOffsetMs: state.elapsedMs });
    setCameraOpen(false); Alert.alert(t('recording.photoSaved'));
  };

  return <View style={styles.page}>
    <Text style={styles.title}>{t('recording.title')}</Text><Text style={styles.address}>{showing.title}</Text>
    <RecordingControls state={state} onResume={() => { void startSegment(); }} onPhoto={() => { void openCamera(); }} onVoiceTag={tag} onEnd={end} />
    <Modal visible={cameraOpen} animationType="slide" onRequestClose={() => setCameraOpen(false)}>
      <CameraView ref={camera} style={styles.camera} facing="back" />
      <View style={styles.cameraBar}><Pressable onPress={() => setCameraOpen(false)}><Text style={styles.cameraText}>{t('common.cancel')}</Text></Pressable><Pressable accessibilityRole="button" style={styles.shutter} onPress={() => { void takePhoto(); }} /><View style={styles.spacer} /></View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream, paddingTop: 58 }, title: { textAlign: 'center', color: colors.ink, fontWeight: '800', fontSize: 20 }, address: { textAlign: 'center', color: colors.muted, marginTop: 5 },
  camera: { flex: 1 }, cameraBar: { height: 130, backgroundColor: colors.black, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingBottom: 20 }, cameraText: { color: colors.white, width: 80 },
  shutter: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.white, borderWidth: 6, borderColor: colors.muted }, spacer: { width: 80 },
});
