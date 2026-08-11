import i18n from './src/i18n';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppState, StyleSheet, View } from 'react-native';
import * as Network from 'expo-network';
import { StatusBar } from 'expo-status-bar';
import { api } from './src/api/client';
import { getTokens } from './src/auth/tokenStore';
import { HomeScreen } from './src/screens/HomeScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { RecordingScreen } from './src/screens/RecordingScreen';
import { ReportScreen } from './src/screens/ReportScreen';
import { captureRepository } from './src/storage/database';
import { SyncEngine, syncStateFromProcessing } from './src/sync/engine';
import type { Contact, LocalShowing, Property, ShowingSummary } from './src/types';

type Screen = { name: 'home' } | { name: 'recording'; showing: LocalShowing; recovered: boolean } | { name: 'report'; visitId: string };

export default function App() {
  const [booting, setBooting] = useState(true); const [authenticated, setAuthenticated] = useState(false); const [screen, setScreen] = useState<Screen>({ name: 'home' });
  const [localShowings, setLocalShowings] = useState<LocalShowing[]>([]); const [remoteShowings, setRemoteShowings] = useState<ShowingSummary[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]); const [properties, setProperties] = useState<Property[]>([]); const [refreshing, setRefreshing] = useState(false);

  const engine = useMemo(() => new SyncEngine(captureRepository, api, {
    isOnline: async () => { const state = await Network.getNetworkStateAsync(); return Boolean(state.isConnected && state.isInternetReachable !== false); },
  }), []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await engine.run();
      const locals = await captureRepository.listShowings(); setLocalShowings(locals);
      try {
        const [showings, nextContacts, nextProperties] = await Promise.all([api.listShowings(), api.listContacts(), api.listProperties()]);
        setRemoteShowings(showings); setContacts(nextContacts); setProperties(nextProperties);
        for (const local of locals) {
          const remote = showings.find((item) => item.id === local.remoteId); if (!remote) continue;
          const syncState = syncStateFromProcessing(remote.processingStatus, local.syncState);
          if (syncState !== local.syncState || remote.processingStatus !== local.processingStatus) await captureRepository.patchShowing(local.id, { syncState, processingStatus: remote.processingStatus, updatedAt: Date.now() });
        }
        setLocalShowings(await captureRepository.listShowings());
      } catch { /* Offline refresh deliberately keeps local captures visible. */ }
    } finally { setRefreshing(false); }
  }, [engine]);

  useEffect(() => { void (async () => {
    const tokens = await getTokens(); setAuthenticated(Boolean(tokens));
    const active = await captureRepository.activeShowing();
    if (active) setScreen({ name: 'recording', showing: active, recovered: true });
    setBooting(false); if (tokens) void refresh();
  })(); }, [refresh]);

  useEffect(() => {
    if (!authenticated) return;
    const timer = setInterval(() => { void refresh(); }, 15_000);
    const subscription = AppState.addEventListener('change', (state) => { if (state === 'active') void refresh(); });
    return () => { clearInterval(timer); subscription.remove(); };
  }, [authenticated, refresh]);

  const recent = useMemo(() => {
    const linked = new Set(localShowings.map((item) => item.remoteId).filter(Boolean));
    const remoteOnly: LocalShowing[] = remoteShowings.filter((item) => !linked.has(item.id)).map((item) => ({
      id: `remote-${item.id}`, remoteId: item.id, contactId: item.contact?.id ?? null, subjectId: item.property?.id ?? null, address: null, consentAck: item.consentAck,
      title: item.property?.displayName ?? i18n.t('home.untitled'), startedAt: new Date(item.createdAt).getTime(), endedAt: null, elapsedMs: 0,
      syncState: syncStateFromProcessing(item.processingStatus, 'synced'),
      processingStatus: item.processingStatus, finishRequested: false, lastError: null, updatedAt: new Date(item.createdAt).getTime(), generation: 0,
    }));
    return [...localShowings, ...remoteOnly].sort((a, b) => b.startedAt - a.startedAt).slice(0, 50);
  }, [localShowings, remoteShowings]);

  if (booting) return <View style={styles.boot}><StatusBar style="dark" /></View>;
  if (!authenticated) return <><LoginScreen onAuthenticated={() => { setAuthenticated(true); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'recording') return <><RecordingScreen showing={screen.showing} recovered={screen.recovered} onFinished={() => { setScreen({ name: 'home' }); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'report') return <><ReportScreen visitId={screen.visitId} onBack={() => setScreen({ name: 'home' })} /><StatusBar style="dark" /></>;
  return <><HomeScreen showings={recent} contacts={contacts} properties={properties} refreshing={refreshing} onRefresh={() => { void refresh(); }} onLogout={() => { void api.logout(); setAuthenticated(false); }} onOpenReport={(visitId) => setScreen({ name: 'report', visitId })} onStart={(input) => { void (async () => { const showing = await captureRepository.createShowing(input); setLocalShowings((items) => [showing, ...items]); setScreen({ name: 'recording', showing, recovered: false }); })(); }} /><StatusBar style="dark" /></>;
}

const styles = StyleSheet.create({ boot: { flex: 1, backgroundColor: '#F5F3EA' } });
