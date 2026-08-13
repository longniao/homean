import i18n from './src/i18n';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, StyleSheet, View } from 'react-native';
import * as Network from 'expo-network';
import { StatusBar } from 'expo-status-bar';
import { api } from './src/api/client';
import { getAccount } from './src/auth/accountStore';
import { getTokens } from './src/auth/tokenStore';
import { HomeScreen } from './src/screens/HomeScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { RecordingScreen } from './src/screens/RecordingScreen';
import { ReportScreen } from './src/screens/ReportScreen';
import { clearCache, readDirectory, writeDirectory } from './src/storage/cache';
import { captureRepository } from './src/storage/database';
import { SyncEngine, syncStateFromProcessing } from './src/sync/engine';
import type { Account, Contact, LocalShowing, Property, ShowingSummary } from './src/types';

type Screen = { name: 'home' } | { name: 'recording'; showing: LocalShowing; recovered: boolean } | { name: 'report'; visitId: string };

export default function App() {
  const [booting, setBooting] = useState(true); const [authenticated, setAuthenticated] = useState(false); const [screen, setScreen] = useState<Screen>({ name: 'home' });
  const [localShowings, setLocalShowings] = useState<LocalShowing[]>([]); const [remoteShowings, setRemoteShowings] = useState<ShowingSummary[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]); const [properties, setProperties] = useState<Property[]>([]); const [refreshing, setRefreshing] = useState(false);
  const [account, setAccount] = useState<Account | null>(null); const accountLoaded = useRef(false);

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
        // Mirror the picker data so the next cold start can offer clients and
        // properties without a network round trip.
        await writeDirectory({ contacts: nextContacts, properties: nextProperties });
        for (const local of locals) {
          const remote = showings.find((item) => item.id === local.remoteId); if (!remote) continue;
          const syncState = syncStateFromProcessing(remote.processingStatus, local.syncState);
          if (syncState !== local.syncState || remote.processingStatus !== local.processingStatus) await captureRepository.patchShowing(local.id, { syncState, processingStatus: remote.processingStatus, updatedAt: Date.now() });
        }
        setLocalShowings(await captureRepository.listShowings());
      } catch { /* Offline refresh deliberately keeps local captures visible. */ }
      // The stored identity outlives a failed fetch, so this only has to run
      // when nothing is cached yet rather than on every poll.
      if (!accountLoaded.current) {
        try { setAccount(await api.loadAccount()); accountLoaded.current = true; } catch { /* the stored identity stands until the next sync */ }
      }
    } finally { setRefreshing(false); }
  }, [engine]);

  useEffect(() => {
    api.onSessionExpired(() => { setAuthenticated(false); setAccount(null); setContacts([]); setProperties([]); setRemoteShowings([]); setScreen({ name: 'home' }); void clearCache(); });
    return () => { api.onSessionExpired(null); };
  }, []);

  useEffect(() => { void (async () => {
    const [tokens, storedAccount, directory] = await Promise.all([getTokens(), getAccount(), readDirectory()]);
    setAuthenticated(Boolean(tokens)); setAccount(storedAccount);
    if (directory) { setContacts(directory.contacts); setProperties(directory.properties); }
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
  if (!authenticated) return <><LoginScreen onAuthenticated={() => { accountLoaded.current = false; setAuthenticated(true); void getAccount().then(setAccount); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'recording') return <><RecordingScreen showing={screen.showing} recovered={screen.recovered} onFinished={() => { setScreen({ name: 'home' }); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'report') return <><ReportScreen visitId={screen.visitId} onBack={() => setScreen({ name: 'home' })} /><StatusBar style="dark" /></>;
  return <><HomeScreen showings={recent} contacts={contacts} properties={properties} account={account} refreshing={refreshing} onRefresh={() => { void refresh(); }} onLogout={() => { void api.logout(); void clearCache(); accountLoaded.current = false; setAccount(null); setContacts([]); setProperties([]); setRemoteShowings([]); setAuthenticated(false); }} onOpenReport={(visitId) => setScreen({ name: 'report', visitId })} onStart={(input) => { void (async () => { const showing = await captureRepository.createShowing(input); setLocalShowings((items) => [showing, ...items]); setScreen({ name: 'recording', showing, recovered: false }); })(); }} /><StatusBar style="dark" /></>;
}

const styles = StyleSheet.create({ boot: { flex: 1, backgroundColor: '#F5F3EA' } });
