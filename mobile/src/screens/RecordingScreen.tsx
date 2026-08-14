import { useEffect, useReducer, useRef, useState } from 'react';
import { Alert, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Directory, File, Paths } from 'expo-file-system';
import { RecordingPresets, requestNotificationPermissionsAsync, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import { useTranslation } from 'react-i18next';
import { RecordingControls } from '../components/RecordingControls';
import { colors } from '../theme';
import { initialRecordingState, recordingReducer } from '../recording/machine';
import { requestCapturePermissions } from '../recording/permissions';
import { recoverInterruptedSegment } from '../recording/recovery';
import { captureRepository } from '../storage/database';
import type { LocalShowing } from '../types';

// Kept under the API's 200 MB ceiling so the recorder stops on its own rather
// than uploading a file the server will refuse.
const VIDEO_MAX_BYTES = 180 * 1024 * 1024;

export function RecordingScreen({ showing, recovered, onFinished }: { showing: LocalShowing; recovered: boolean; onFinished: () => void }) {
  const { t } = useTranslation();
  const [state, dispatch] = useReducer(recordingReducer, recovered ? { ...initialRecordingState, phase: 'interrupted', elapsedMs: showing.elapsedMs, segmentStartedAtMs: showing.elapsedMs } : initialRecordingState);
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, directory: 'document' }, (status) => {
    if (status.hasError || status.mediaServicesDidReset) dispatch({ type: 'INTERRUPTED', error: status.error ?? undefined });
  });
  const recorderState = useAudioRecorderState(recorder, 500); const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraMode, setCameraMode] = useState<'picture' | 'video'>('picture'); const [cameraReady, setCameraReady] = useState(false);
  const [videoRecording, setVideoRecording] = useState(false);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions(); const camera = useRef<CameraView>(null); const starting = useRef(false);
  const [recoveryStatus, setRecoveryStatus] = useState<'pending' | 'ready' | 'failed'>(recovered ? 'pending' : 'ready');
  const recoveryStatusRef = useRef<'pending' | 'ready' | 'failed'>(recovered ? 'pending' : 'ready');
  const recoveryPromise = useRef<Promise<void> | null>(null);
  const ending = useRef(false);

  useEffect(() => {
    if (!recovered) return;
    let cancelled = false;
    recoveryStatusRef.current = 'pending';
    const pending = recoverInterruptedSegment(captureRepository, showing.id, (fileUri) => new File(fileUri).exists);
    recoveryPromise.current = pending;
    void pending.then(() => {
      if (cancelled) return;
      recoveryStatusRef.current = 'ready';
      setRecoveryStatus('ready');
    }).catch((error: unknown) => {
      if (cancelled) return;
      recoveryStatusRef.current = 'failed';
      setRecoveryStatus('failed');
      dispatch({ type: 'FAIL', error: error instanceof Error ? error.message : t('recording.recoveryFailed') });
    });
    return () => {
      cancelled = true;
      if (recoveryPromise.current === pending) recoveryPromise.current = null;
    };
    // Recovery is tied to the showing mount, not to phase changes caused by
    // Resume. Re-running it after Resume would race the active recorder.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recovered, showing.id]);

  useEffect(() => {
    if (state.phase !== 'recording') return;
    const elapsed = state.segmentStartedAtMs + recorderState.durationMillis;
    dispatch({ type: 'TICK', elapsedMs: elapsed });
    void captureRepository.updateElapsed(showing.id, elapsed);
  }, [recorderState.durationMillis, showing.id, state.phase, state.segmentStartedAtMs]);

  async function closeSegment() {
    const offset = state.segmentStartedAtMs;
    try { if (recorder.isRecording) await recorder.stop(); } catch { /* preserve any file the recorder produced */ }
    if (recorder.uri && new File(recorder.uri).exists) await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'audio', fileUri: recorder.uri, contentType: 'audio/mp4', timestampOffsetMs: offset });
    await captureRepository.clearRecordingSession(showing.id);
  }

  async function startSegment() {
    if (starting.current || (recovered && recoveryStatusRef.current !== 'ready')) return;
    starting.current = true; const previousPhase = state.phase; dispatch({ type: previousPhase === 'idle' ? 'START' : 'RESUME' });
    try {
      if (previousPhase === 'interrupted' || previousPhase === 'error') await closeSegment();
      const permission = await requestCapturePermissions({
        platformOS: Platform.OS,
        platformVersion: Platform.Version,
        requestRecording: requestRecordingPermissionsAsync,
        requestNotifications: requestNotificationPermissionsAsync,
      });
      if (!permission.granted) {
        const message = permission.failure === 'notifications' ? t('recording.notificationPermission') : t('recording.permission');
        Alert.alert(message); dispatch({ type: 'FAIL', error: message }); return;
      }
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

  async function waitForRecovery(): Promise<boolean> {
    const pending = recoveryPromise.current;
    if (pending) {
      try { await pending; } catch { return false; }
    }
    return recoveryStatusRef.current === 'ready';
  }

  async function finishShowing() {
    if (ending.current) return;
    ending.current = true;
    try {
      // End must wait for the prior segment to be queued too; otherwise an
      // immediate End tap could clear the recovery row before enqueueMedia.
      if (!(await waitForRecovery())) { Alert.alert(t('recording.recoveryFailed')); return; }
      dispatch({ type: 'STOP' }); await closeSegment(); await captureRepository.finish(showing.id, state.elapsedMs); dispatch({ type: 'STOPPED' }); onFinished();
    } finally { ending.current = false; }
  }

  const end = () => Alert.alert(t('recording.endTitle'), t('recording.endBody'), [
    { text: t('common.cancel'), style: 'cancel' },
    { text: t('recording.endConfirm'), style: 'destructive', onPress: () => { void finishShowing(); } },
  ]);
  const tag = () => { void captureRepository.addVoiceTag(showing.id, state.elapsedMs); Alert.alert(t('recording.tagged')); };
  const openCamera = async (mode: 'photo' | 'video') => {
    if (!cameraPermission?.granted && !(await requestCameraPermission()).granted) { Alert.alert(t('recording.cameraPermission')); return; }
    setCameraMode(mode === 'photo' ? 'picture' : 'video'); setCameraReady(false); setCameraOpen(true);
  };
  const takePhoto = async () => {
    const result = await camera.current?.takePictureAsync({ quality: 0.85 }); if (!result) return;
    const directory = new Directory(Paths.document, 'showing-photos'); if (!directory.exists) directory.create({ idempotent: true, intermediates: true });
    const destination = new File(directory, `${showing.id}-${Date.now()}.jpg`); await new File(result.uri).copy(destination);
    await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'photo', fileUri: destination.uri, contentType: 'image/jpeg', timestampOffsetMs: state.elapsedMs });
    setCameraOpen(false); Alert.alert(t('recording.photoSaved'));
  };
  const saveVideo = async (uri: string, timestampOffsetMs: number) => {
    const sourceExtension = uri.match(/\.([a-z0-9]+)(?:\?.*)?$/i)?.[1]?.toLowerCase() ?? 'mp4';
    const extension = sourceExtension === 'mov' || sourceExtension === 'webm' ? sourceExtension : 'mp4';
    const contentType = extension === 'mov' ? 'video/quicktime' : extension === 'webm' ? 'video/webm' : 'video/mp4';
    const directory = new Directory(Paths.document, 'showing-videos'); if (!directory.exists) directory.create({ idempotent: true, intermediates: true });
    const destination = new File(directory, `${showing.id}-${Date.now()}.${extension}`); await new File(uri).copy(destination);
    await captureRepository.enqueueMedia({ showingId: showing.id, kind: 'video', fileUri: destination.uri, contentType, timestampOffsetMs });
    Alert.alert(t('recording.videoSaved'));
  };
  const startVideo = async () => {
    if (videoRecording || !camera.current || !cameraReady) return;
    const offset = state.elapsedMs; setVideoRecording(true);
    try {
      const result = await camera.current.recordAsync({
        // Bound the actual problem — bytes — rather than guessing a duration.
        // A hard time limit truncates whoever is still explaining a defect,
        // and that explanation is the evidence. Set below the server's ceiling
        // so the recorder stops before an upload could be rejected.
        maxFileSize: VIDEO_MAX_BYTES,
        // Only a runaway guard: the recorder is modal and stopping is manual,
        // but a phone pocketed mid-recording should not film until it dies.
        maxDuration: 600,
      });
      if (!result) throw new Error(t('common.error'));
      await saveVideo(result.uri, offset); setCameraOpen(false);
    } catch (error) {
      Alert.alert(error instanceof Error ? error.message : t('common.error'));
    } finally { setVideoRecording(false); }
  };
  const stopVideo = () => { if (videoRecording) void camera.current?.stopRecording(); };
  const closeCamera = () => { if (videoRecording) { stopVideo(); return; } setCameraOpen(false); };

  // Keep camera video muted: expo-audio owns the continuous showing microphone/evidence chain.
  return <View style={styles.page}>
    <Text style={styles.title}>{t('recording.title')}</Text><Text style={styles.address}>{showing.title}</Text>
    <RecordingControls state={state} resumeDisabled={recoveryStatus !== 'ready'} onResume={() => { void startSegment(); }} onPhoto={() => { void openCamera('photo'); }} onVideo={() => { void openCamera('video'); }} onVoiceTag={tag} onEnd={end} />
    <Modal visible={cameraOpen} animationType="slide" onRequestClose={closeCamera}>
      <CameraView ref={camera} style={styles.camera} facing="back" mode={cameraMode} videoQuality="720p" mute={cameraMode === 'video'} onCameraReady={() => setCameraReady(true)} />
      <View style={styles.cameraBar}>
        <Pressable onPress={closeCamera} disabled={videoRecording}><Text style={styles.cameraText}>{t('common.cancel')}</Text></Pressable>
        {cameraMode === 'picture' ? <Pressable accessibilityRole="button" accessibilityLabel={t('recording.photo')} style={styles.shutter} onPress={() => { void takePhoto(); }} disabled={!cameraReady} /> : <Pressable accessibilityRole="button" accessibilityLabel={videoRecording ? t('recording.stopVideo') : t('recording.startVideo')} style={[styles.shutter, videoRecording && styles.videoShutter]} onPress={videoRecording ? stopVideo : () => { void startVideo(); }} disabled={!cameraReady} />}
        <View style={styles.spacer} />
      </View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream, paddingTop: 58 }, title: { textAlign: 'center', color: colors.ink, fontWeight: '800', fontSize: 20 }, address: { textAlign: 'center', color: colors.muted, marginTop: 5 },
  camera: { flex: 1 }, cameraBar: { height: 130, backgroundColor: colors.black, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingBottom: 20 }, cameraText: { color: colors.white, width: 80 },
  shutter: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.white, borderWidth: 6, borderColor: colors.muted }, videoShutter: { backgroundColor: colors.red, borderColor: colors.white }, spacer: { width: 80 },
});
