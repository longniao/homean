import i18n from './src/i18n';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, StyleSheet, View } from 'react-native';
import * as Network from 'expo-network';
import { StatusBar } from 'expo-status-bar';
import { api } from './src/api/client';
import { activateSessionAccount, currentSessionAccount, sessionGeneration, assertSessionGeneration } from './src/auth/sessionScope';
import { getTokens } from './src/auth/tokenStore';
import { HomeScreen } from './src/screens/HomeScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { RecordingScreen } from './src/screens/RecordingScreen';
import { ReportScreen } from './src/screens/ReportScreen';
import { clearCache, readDirectory, readVerticalConfig, writeDirectory, writeVerticalConfig } from './src/storage/cache';
import { captureRepository, repositoryForAccount } from './src/storage/database';
import { SyncEngine, syncStateFromProcessing } from './src/sync/engine';
import type { Account, ConsentPolicy, Contact, LocalShowing, Property, ShowingSummary } from './src/types';

type Screen = { name: 'home' } | { name: 'recording'; showing: LocalShowing; recovered: boolean } | { name: 'report'; visitId: string };

export default function App() {
  const [booting, setBooting] = useState(true); const [authenticated, setAuthenticated] = useState(false); const [screen, setScreen] = useState<Screen>({ name: 'home' });
  const [localShowings, setLocalShowings] = useState<LocalShowing[]>([]); const [remoteShowings, setRemoteShowings] = useState<ShowingSummary[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]); const [properties, setProperties] = useState<Property[]>([]); const [refreshing, setRefreshing] = useState(false);
  const [account, setAccount] = useState<Account | null>(null);
  const [consent, setConsent] = useState<ConsentPolicy | null>(null);

  const syncRef = useRef<{ generation: number; engine: SyncEngine } | null>(null);
  const refresh = useCallback(async () => {
    let owner: Account;
    try { owner = currentSessionAccount(); } catch { return; }
    const generation = sessionGeneration();
    const repository = repositoryForAccount(owner);
    const client = api.forCurrentSession();
    if (syncRef.current?.generation !== generation) {
      syncRef.current = { generation, engine: new SyncEngine(repository, client, {
        isOnline: async () => {
          assertSessionGeneration(generation);
          const state = await Network.getNetworkStateAsync();
          assertSessionGeneration(generation);
          return Boolean(state.isConnected && state.isInternetReachable !== false);
        },
      }) };
    }
    setRefreshing(true);
    try {
      await syncRef.current.engine.run();
      assertSessionGeneration(generation);
      const locals = await repository.listShowings();
      assertSessionGeneration(generation);
      setLocalShowings(locals);
      const [showings, nextContacts, nextProperties, verticalConfig] = await Promise.all([
        client.listShowings(), client.listContacts(), client.listProperties(), client.getVerticalConfig(),
      ]);
      assertSessionGeneration(generation);
      setRemoteShowings(showings); setContacts(nextContacts); setProperties(nextProperties);
      setConsent(verticalConfig.consent);
      await writeDirectory({ contacts: nextContacts, properties: nextProperties });
      assertSessionGeneration(generation);
      await writeVerticalConfig(verticalConfig);
      for (const local of locals) {
        assertSessionGeneration(generation);
        const remote = showings.find((item) => item.id === local.remoteId); if (!remote) continue;
        const syncState = syncStateFromProcessing(remote.processingStatus, local.syncState);
        if (syncState !== local.syncState || remote.processingStatus !== local.processingStatus) await repository.patchShowing(local.id, { syncState, processingStatus: remote.processingStatus, updatedAt: Date.now() });
      }
      const updated = await repository.listShowings();
      assertSessionGeneration(generation);
      setLocalShowings(updated);
    } catch { /* Offline data stays with its original account; stale sessions cannot update UI. */ }
    finally { if (sessionGeneration() === generation) setRefreshing(false); }
  }, []);

  useEffect(() => {
    api.onSessionExpired(() => { setAuthenticated(false); setAccount(null); setContacts([]); setProperties([]); setRemoteShowings([]); setLocalShowings([]); setConsent(null); setScreen({ name: 'home' }); void clearCache(); });
    return () => { api.onSessionExpired(null); };
  }, []);

  useEffect(() => { void (async () => {
    try {
      const tokens = await getTokens();
      if (!tokens) return;
      const owner = tokens.account ?? await api.loadAccount();
      activateSessionAccount(owner);
      const generation = sessionGeneration();
      const [directory, cachedConfig, active] = await Promise.all([
        readDirectory(), readVerticalConfig(), captureRepository.activeShowing(),
      ]);
      assertSessionGeneration(generation);
      setAccount(owner); setAuthenticated(true);
      if (cachedConfig) setConsent(cachedConfig.consent);
      if (directory) { setContacts(directory.contacts); setProperties(directory.properties); }
      if (active) setScreen({ name: 'recording', showing: active, recovered: true });
      void refresh();
    } catch { /* An unidentified session must sign in before reading captures. */ }
    finally { setBooting(false); }
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
      title: item.property?.displayName ?? i18n.t('home.untitled'), startedAt: new Date(item.startedAt ?? item.createdAt).getTime(), endedAt: null, elapsedMs: 0,
      syncState: syncStateFromProcessing(item.processingStatus, 'synced'),
      processingStatus: item.processingStatus, finishRequested: false, lastError: null, updatedAt: new Date(item.createdAt).getTime(), generation: 0,
    }));
    return [...localShowings, ...remoteOnly].sort((a, b) => b.startedAt - a.startedAt).slice(0, 50);
  }, [localShowings, remoteShowings]);

  if (booting) return <View style={styles.boot}><StatusBar style="dark" /></View>;
  if (!authenticated) return <><LoginScreen onAuthenticated={() => { setAccount(currentSessionAccount()); setAuthenticated(true); setLocalShowings([]); setScreen({ name: 'home' }); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'recording') return <><RecordingScreen showing={screen.showing} recovered={screen.recovered} onFinished={() => { setScreen({ name: 'home' }); void refresh(); }} /><StatusBar style="dark" /></>;
  if (screen.name === 'report') return <><ReportScreen visitId={screen.visitId} onBack={() => setScreen({ name: 'home' })} /><StatusBar style="dark" /></>;
  return <><HomeScreen showings={recent} contacts={contacts} properties={properties} account={account} consent={consent} refreshing={refreshing} onRefresh={() => { void refresh(); }} onLogout={() => { void clearCache(); void api.logout(); setLocalShowings([]); setScreen({ name: 'home' }); setAccount(null); setContacts([]); setProperties([]); setRemoteShowings([]); setConsent(null); setAuthenticated(false); }} onOpenReport={(visitId) => setScreen({ name: 'report', visitId })} onStart={(input) => { void (async () => { const generation = sessionGeneration(); const showing = await captureRepository.createShowing(input); if (sessionGeneration() !== generation) return; setLocalShowings((items) => [showing, ...items]); setScreen({ name: 'recording', showing, recovered: false }); })(); }} /><StatusBar style="dark" /></>;
}

const styles = StyleSheet.create({ boot: { flex: 1, backgroundColor: '#F5F3EA' } });
