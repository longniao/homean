import { useMemo, useState } from 'react';
import { Modal, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Card, PrimaryButton, SecondaryButton } from '../components/ui';
import { colors } from '../theme';
import type { Contact, LocalShowing, Property } from '../types';

interface Props {
  showings: LocalShowing[]; contacts: Contact[]; properties: Property[]; refreshing: boolean;
  onRefresh: () => void; onLogout: () => void;
  onStart: (input: { contactId: string | null; subjectId: string | null; address: string | null; title: string }) => void;
  onOpenReport: (remoteId: string) => void;
}

export function HomeScreen(props: Props) {
  const { t } = useTranslation(); const [setup, setSetup] = useState(false); const [query, setQuery] = useState('');
  const [contactId, setContactId] = useState<string | null>(null); const [subjectId, setSubjectId] = useState<string | null>(null); const [address, setAddress] = useState('');
  const contacts = useMemo(() => props.contacts.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())), [props.contacts, query]);
  const properties = useMemo(() => props.properties.filter((item) => `${item.displayName} ${item.address}`.toLowerCase().includes(query.toLowerCase())), [props.properties, query]);
  const begin = () => {
    const property = props.properties.find((item) => item.id === subjectId);
    props.onStart({ contactId, subjectId, address: subjectId ? null : address.trim() || null, title: property?.displayName ?? (address.trim() || t('home.untitled')) });
    setSetup(false); setQuery(''); setContactId(null); setSubjectId(null); setAddress('');
  };
  return <View style={styles.page}>
    <View style={styles.header}><Text style={styles.title}>{t('home.title')}</Text><Pressable onPress={props.onLogout}><Text style={styles.logout}>{t('home.signOut')}</Text></Pressable></View>
    <PrimaryButton label={t('home.start')} onPress={() => setSetup(true)} style={styles.start} />
    <SecondaryButton label={t('home.syncNow')} onPress={props.onRefresh} style={styles.sync} />
    <Text style={styles.section}>{t('home.recent')}</Text>
    <ScrollView refreshControl={<RefreshControl refreshing={props.refreshing} onRefresh={props.onRefresh} />} contentContainerStyle={styles.list}>
      {props.showings.length === 0 ? <Text style={styles.empty}>{t('home.empty')}</Text> : props.showings.map((item) => <Card key={item.id} style={styles.showing}>
        <View style={styles.row}><View style={styles.grow}><Text style={styles.showingTitle}>{item.title}</Text><Text style={styles.date}>{new Date(item.startedAt).toLocaleDateString('en')}</Text></View><View style={[styles.badge, item.syncState === 'failed' && styles.failed]}><Text style={styles.badgeText}>{t(`sync.${item.syncState}`)}</Text></View></View>
        {item.lastError && <Text style={styles.error}>{t('sync.failed')}</Text>}
        {item.remoteId && item.syncState === 'ready' && <SecondaryButton label={t('home.report')} onPress={() => props.onOpenReport(item.remoteId!)} style={styles.reportButton} />}
      </Card>)}
    </ScrollView>
    <Modal visible={setup} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setSetup(false)}>
      <ScrollView style={styles.modal} contentContainerStyle={styles.modalContent}>
        <View style={styles.header}><Text style={styles.title}>{t('setup.title')}</Text><Pressable onPress={() => setSetup(false)}><Text>{t('common.close')}</Text></Pressable></View>
        <TextInput style={styles.input} placeholder={t('setup.search')} value={query} onChangeText={setQuery} />
        <Text style={styles.label}>{t('setup.client')}</Text><Choice selected={contactId === null} label={t('setup.noClient')} onPress={() => setContactId(null)} />
        {contacts.map((item) => <Choice key={item.id} selected={contactId === item.id} label={item.name} onPress={() => setContactId(item.id)} />)}
        <Text style={styles.label}>{t('setup.property')}</Text><Choice selected={subjectId === null && !address} label={t('setup.noProperty')} onPress={() => { setSubjectId(null); setAddress(''); }} />
        {properties.map((item) => <Choice key={item.id} selected={subjectId === item.id} label={`${item.displayName} · ${item.address}`} onPress={() => { setSubjectId(item.id); setAddress(''); }} />)}
        <Text style={styles.label}>{t('setup.address')}</Text><TextInput style={styles.input} placeholder={t('setup.addressPlaceholder')} value={address} onChangeText={(value) => { setAddress(value); if (value) setSubjectId(null); }} />
        <PrimaryButton label={t('setup.begin')} onPress={begin} style={styles.begin} />
      </ScrollView>
    </Modal>
  </View>;
}

function Choice({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return <Pressable onPress={onPress} style={[styles.choice, selected && styles.choiceSelected]}><View style={[styles.radio, selected && styles.radioSelected]} /><Text style={styles.choiceText}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream, paddingTop: 58 }, header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 22 },
  title: { fontSize: 27, fontWeight: '800', color: colors.ink }, logout: { color: colors.green, fontWeight: '700' }, start: { margin: 22, marginBottom: 10, minHeight: 92, borderRadius: 24 }, sync: { marginHorizontal: 22, marginBottom: 22 },
  section: { marginHorizontal: 22, marginBottom: 10, color: colors.ink, fontSize: 19, fontWeight: '700' }, list: { paddingHorizontal: 22, paddingBottom: 40, gap: 12 }, empty: { color: colors.muted, textAlign: 'center', paddingTop: 40, lineHeight: 24 },
  showing: { gap: 12 }, row: { flexDirection: 'row', alignItems: 'center', gap: 12 }, grow: { flex: 1 }, showingTitle: { fontSize: 17, fontWeight: '700', color: colors.ink }, date: { color: colors.muted, marginTop: 4 },
  badge: { backgroundColor: colors.greenSoft, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 6 }, failed: { backgroundColor: colors.redSoft }, badgeText: { color: colors.ink, fontWeight: '600', fontSize: 12 }, error: { color: colors.red }, reportButton: { alignSelf: 'flex-start' },
  modal: { flex: 1, backgroundColor: colors.cream }, modalContent: { paddingTop: 28, paddingBottom: 50 }, input: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14, fontSize: 16, margin: 22, marginBottom: 8 },
  label: { marginHorizontal: 22, marginTop: 22, marginBottom: 8, fontWeight: '700', color: colors.ink }, choice: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: 22, paddingVertical: 11 }, choiceSelected: { backgroundColor: colors.greenSoft, borderRadius: 10, paddingHorizontal: 10 },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.border }, radioSelected: { borderWidth: 6, borderColor: colors.green }, choiceText: { flex: 1, color: colors.ink }, begin: { margin: 22, marginTop: 34 },
});
