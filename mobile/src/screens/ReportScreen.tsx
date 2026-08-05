import { useEffect, useMemo, useState } from 'react';
import { Alert, Linking, Modal, Pressable, ScrollView, Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import { Card, PrimaryButton, SecondaryButton } from '../components/ui';
import { colors } from '../theme';
import type { ReportBullet, ReportContent, ShowingDetail } from '../types';

type BulletLocation = { group: 'highlights' | 'concerns' | 'follow_ups'; index: number } | { group: 'room_by_room'; room: number; index: number };

export function ReportScreen({ visitId, onBack }: { visitId: string; onBack: () => void }) {
  const { t } = useTranslation(); const [detail, setDetail] = useState<ShowingDetail | null>(null); const [loading, setLoading] = useState(true);
  const [edit, setEdit] = useState<{ location: BulletLocation; value: string } | null>(null);
  const load = async () => { setLoading(true); try { setDetail(await api.getShowing(visitId)); } catch { Alert.alert(t('common.error')); } finally { setLoading(false); } };
  useEffect(() => {
    let active = true;
    void api.getShowing(visitId).then((value) => { if (active) setDetail(value); }).catch(() => Alert.alert(t('common.error'))).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [t, visitId]);
  const canConfirm = useMemo(() => {
    if (!detail?.report || !detail.property) return false;
    const reviewed = detail.observations.some((item) => item.reviewStatus !== 'pending');
    const pendingSensitive = detail.observations.some((item) => item.flags.sensitive && item.reviewStatus === 'pending');
    return reviewed && !pendingSensitive;
  }, [detail]);

  const saveBullet = async () => {
    if (!detail?.report || !edit?.value.trim()) return;
    const content = JSON.parse(JSON.stringify(detail.report.content)) as ReportContent;
    if (edit.location.group === 'room_by_room') content.room_by_room[edit.location.room]!.bullets[edit.location.index]!.text = edit.value.trim();
    else content[edit.location.group][edit.location.index]!.text = edit.value.trim();
    try { await api.updateReport(detail.report.id, content); setDetail({ ...detail, report: { ...detail.report, content } }); setEdit(null); Alert.alert(t('report.saved')); } catch { Alert.alert(t('common.error')); }
  };
  const dismiss = async (id: string) => { try { await api.dismissObservation(id); await load(); Alert.alert(t('report.dismissed')); } catch { Alert.alert(t('common.error')); } };
  const confirm = async () => { try { await api.confirmShowing(visitId); await load(); } catch { Alert.alert(t('common.error')); } };
  const send = async () => { try { const url = await api.createShareLink(visitId); await Share.share({ message: url, url }); Alert.alert(t('report.shared')); } catch { Alert.alert(t('common.error')); } };
  const desktop = () => { const base = (process.env.EXPO_PUBLIC_DASHBOARD_URL ?? 'http://localhost:3000').replace(/\/$/, ''); void Linking.openURL(`${base}/showings/${visitId}`); };

  if (loading || !detail) return <View style={styles.center}><Text>{t('common.loading')}</Text></View>;
  if (!detail.report) return <View style={styles.center}><Text>{t('report.noReport')}</Text><SecondaryButton label={t('common.back')} onPress={onBack} /></View>;
  const report = detail.report.content;
  return <View style={styles.page}>
    <View style={styles.header}><Pressable onPress={onBack}><Text style={styles.link}>{t('common.back')}</Text></Pressable><Text style={styles.title}>{t('report.title')}</Text><View style={styles.headerSpace} /></View>
    <ScrollView contentContainerStyle={styles.content}>
      <ReportSection title={t('report.summary')}><Text style={styles.summary}>{report.executive_summary}</Text></ReportSection>
      <ReportSection title={t('report.highlights')}><BulletList bullets={report.highlights} onEdit={(index, bullet) => setEdit({ location: { group: 'highlights', index }, value: bullet.text })} /></ReportSection>
      <ReportSection title={t('report.concerns')}><BulletList bullets={report.concerns} onEdit={(index, bullet) => setEdit({ location: { group: 'concerns', index }, value: bullet.text })} /></ReportSection>
      <Text style={styles.sectionTitle}>{t('report.rooms')}</Text>{report.room_by_room.map((room, roomIndex) => <Card key={`${room.zone_id}-${roomIndex}`} style={styles.card}><Text style={styles.roomTitle}>{room.zone_type ?? t('home.untitled')}</Text><BulletList bullets={room.bullets} onEdit={(index, bullet) => setEdit({ location: { group: 'room_by_room', room: roomIndex, index }, value: bullet.text })} /></Card>)}
      <ReportSection title={t('report.followUps')}><BulletList bullets={report.follow_ups} onEdit={(index, bullet) => setEdit({ location: { group: 'follow_ups', index }, value: bullet.text })} /></ReportSection>
      <Text style={styles.sectionTitle}>{t('report.observations')}</Text>{detail.observations.filter((item) => item.reviewStatus !== 'dismissed').map((item) => <Card key={item.id} style={[styles.card, item.flags.sensitive ? styles.sensitive : undefined]}>
        <Text style={styles.category}>{item.category}</Text><Text style={styles.observation}>{item.content}</Text>{item.flags.sensitive && <Text style={styles.warning}>{t('report.sensitive')}</Text>}
        <SecondaryButton label={t('report.deleteObservation')} onPress={() => { void dismiss(item.id); }} style={styles.delete} textStyle={styles.deleteText} />
      </Card>)}
      {detail.status === 'draft' && (canConfirm ? <PrimaryButton label={t('report.confirm')} onPress={() => { void confirm(); }} /> : <Card style={styles.desktop}><Text style={styles.desktopBody}>{detail.property ? t('report.desktopBody') : t('report.propertyRequired')}</Text><SecondaryButton label={t('report.desktop')} onPress={desktop} /></Card>)}
      {detail.status !== 'draft' && <PrimaryButton label={t('report.send')} onPress={() => { void send(); }} />}
    </ScrollView>
    <Modal visible={Boolean(edit)} transparent animationType="fade" onRequestClose={() => setEdit(null)}><View style={styles.overlay}><Card style={styles.editor}><Text style={styles.sectionTitle}>{t('report.edit')}</Text><TextInput multiline value={edit?.value ?? ''} onChangeText={(value) => setEdit((current) => current ? { ...current, value } : null)} style={styles.input} /><PrimaryButton label={t('common.save')} onPress={() => { void saveBullet(); }} /><SecondaryButton label={t('common.cancel')} onPress={() => setEdit(null)} /></Card></View></Modal>
  </View>;
}

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) { return <View><Text style={styles.sectionTitle}>{title}</Text><Card style={styles.card}>{children}</Card></View>; }
function BulletList({ bullets, onEdit }: { bullets: ReportBullet[]; onEdit: (index: number, bullet: ReportBullet) => void }) {
  const { t } = useTranslation(); return <View style={styles.bullets}>{bullets.map((bullet, index) => <View key={`${bullet.text}-${index}`} style={styles.bulletRow}><Text style={styles.dot}>•</Text><Text style={styles.bulletText}>{bullet.text}</Text><Pressable onPress={() => onEdit(index, bullet)}><Text style={styles.edit}>{t('report.edit')}</Text></Pressable></View>)}</View>;
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.cream, paddingTop: 58 }, center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 18, backgroundColor: colors.cream },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingBottom: 14 }, link: { color: colors.green, fontWeight: '700' }, title: { fontSize: 20, fontWeight: '800', color: colors.ink }, headerSpace: { width: 42 },
  content: { padding: 18, paddingBottom: 60, gap: 16 }, sectionTitle: { color: colors.ink, fontSize: 18, fontWeight: '800', marginBottom: 8 }, card: { gap: 10 }, summary: { color: colors.ink, lineHeight: 22 },
  bullets: { gap: 12 }, bulletRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 }, dot: { color: colors.green, fontSize: 18 }, bulletText: { flex: 1, color: colors.ink, lineHeight: 21 }, edit: { color: colors.green, fontSize: 12, fontWeight: '700' },
  roomTitle: { fontWeight: '800', color: colors.ink, textTransform: 'capitalize' }, category: { color: colors.gold, fontWeight: '800', textTransform: 'uppercase', fontSize: 11 }, observation: { color: colors.ink, lineHeight: 21 }, warning: { color: colors.red, fontWeight: '700' },
  sensitive: { backgroundColor: colors.redSoft, borderColor: colors.red }, delete: { alignSelf: 'flex-start' }, deleteText: { color: colors.red }, desktop: { backgroundColor: colors.greenSoft, gap: 12 }, desktopBody: { color: colors.ink, lineHeight: 21 },
  overlay: { flex: 1, backgroundColor: '#00000066', justifyContent: 'center', padding: 24 }, editor: { gap: 12 }, input: { minHeight: 120, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12, textAlignVertical: 'top' },
});
