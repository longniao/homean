"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Building2,
  Check,
  CircleDot,
  Clock3,
  Copy,
  ExternalLink,
  FileDown,
  ImageIcon,
  Link2,
  LoaderCircle,
  Mail,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  Send,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { ReportEditor } from "@/components/report-editor";
import { StatusBadge } from "@/components/status-badge";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import {
  ApiError,
  api,
  getPublicReportPdfUrl,
  type Delivery,
  type Observation,
  type ReportContent,
  type ShowingDetail,
} from "@/lib/api";
import { copyTextToClipboard } from "@/lib/clipboard";
import { cn } from "@/lib/utils";
import { tourDate } from "@/lib/tour-date";

type Tab = "report" | "observations" | "transcript";
type ShareLink = Delivery["share_links"][number];

const MAX_EXPIRY_TIMER_MS = 60_000;

function isActiveShareLink(link: ShareLink, now: number) {
  return (
    !link.revoked &&
    (link.expires_at === null || new Date(link.expires_at).getTime() > now)
  );
}

function shareLinkStatus(link: ShareLink, now: number) {
  if (link.revoked) return "revoked" as const;
  return isActiveShareLink(link, now) ? "active" as const : "expired" as const;
}

function cacheObservation(
  detail: ShowingDetail | undefined,
  observation: Observation,
) {
  if (!detail) return detail;
  return {
    ...detail,
    observations: detail.observations.map((item) =>
      item.id === observation.id ? observation : item,
    ),
  };
}

function PhotoThumb({ visitId, mediaId }: { visitId: string; mediaId: string }) {
  const t = useTranslations("Showing");
  const download = useQuery({
    queryKey: ["media", visitId, mediaId],
    queryFn: () => api.showings.mediaDownload(visitId, mediaId),
    staleTime: 10 * 60_000,
  });
  return download.data ? (
    // Presigned URLs are dynamic and intentionally bypass Next image optimization.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      alt={t("photoAlt")}
      className="aspect-[4/3] w-36 shrink-0 rounded-xl object-cover"
      src={download.data.download_url}
    />
  ) : (
    <div className="flex aspect-[4/3] w-36 shrink-0 items-center justify-center rounded-xl bg-stone-100 text-stone-400">
      <ImageIcon className="size-5" />
    </div>
  );
}

function ProcessingBanner({ showing }: { showing: ShowingDetail }) {
  const t = useTranslations("Showing");
  const toast = useToast();
  const queryClient = useQueryClient();
  const reprocess = useMutation({
    mutationFn: () => api.showings.reprocess(showing.id),
    onSuccess: () => {
      toast.success(t("reprocessStarted"));
      queryClient.invalidateQueries({ queryKey: ["showing", showing.id] });
    },
    onError: (error) => toast.error(error.message),
  });
  if (showing.processing_status === "ready") return null;
  const failed = showing.processing_status === "failed";
  return (
    <div className={cn("mb-6 flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center", failed ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50")}>
      {failed ? <AlertCircle className="size-5 shrink-0 text-red-700" /> : <LoaderCircle className="size-5 shrink-0 animate-spin text-amber-700" />}
      <div className="flex-1">
        <p className="font-semibold">{failed ? t("processingFailed") : t("processingTitle")}</p>
        <p className="mt-0.5 text-sm text-stone-600">{failed ? showing.processing_error ?? t("processingFailedBody") : t("processingBody")}</p>
      </div>
      {failed && (
        <Button disabled={reprocess.isPending} onClick={() => reprocess.mutate()} variant="outline">
          <RefreshCw className={cn(reprocess.isPending && "animate-spin")} /> {t("reprocess")}
        </Button>
      )}
    </div>
  );
}

function ObservationCard({
  observation,
  showing,
  categories,
  categoryLabels,
  zoneLabels,
  onEvidence,
}: {
  observation: Observation;
  showing: ShowingDetail;
  categories: string[];
  categoryLabels: Record<string, string>;
  zoneLabels: Record<string, string>;
  onEvidence: (observation: Observation) => void;
}) {
  const t = useTranslations("Observations");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(observation.content);
  const [category, setCategory] = useState(observation.category);
  const [zoneId, setZoneId] = useState(observation.zone_id ?? "");
  const queryKey = ["showing", showing.id];

  const update = useMutation({
    mutationFn: () => api.observations.update(observation.id, { content, category, zone_id: zoneId || null }),
    onSuccess: (item) => {
      queryClient.setQueryData<ShowingDetail>(queryKey, (current) => cacheObservation(current, item));
      setEditing(false);
      toast.success(t("updated"));
    },
    onError: (error) => toast.error(error.message),
  });
  const review = useMutation({
    mutationFn: (action: "confirm" | "dismiss") => api.observations[action](observation.id),
    onMutate: async (action) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<ShowingDetail>(queryKey);
      queryClient.setQueryData<ShowingDetail>(queryKey, (current) =>
        current
          ? cacheObservation(current, { ...observation, review_status: action === "confirm" ? "confirmed" : "dismissed" })
          : current,
      );
      return { previous };
    },
    onError: (error, _action, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
      toast.error(error.message);
    },
    onSuccess: (item) => queryClient.setQueryData<ShowingDetail>(queryKey, (current) => cacheObservation(current, item)),
  });
  const sensitive = observation.flags.sensitive === true;
  const readOnly = showing.status !== "draft";

  return (
    <article className={cn("rounded-2xl border bg-white p-4", sensitive && "border-amber-300 bg-amber-50/50", observation.review_status === "dismissed" && "opacity-55")}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-700">{categoryLabels[observation.category]}</span>
        <span className="rounded-full border px-2 py-1 text-xs font-medium text-stone-500">{t(`review.${observation.review_status}` as never)}</span>
        {sensitive && <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900"><ShieldAlert className="size-3" /> {t("sensitive")}</span>}
      </div>
      {editing ? (
        <div className="space-y-3">
          <textarea className="field-area" onChange={(event) => setContent(event.target.value)} value={content} />
          <div className="grid gap-2 sm:grid-cols-2">
            <select className="field" onChange={(event) => setCategory(event.target.value)} value={category}>
              {categories.map((item) => <option key={item} value={item}>{categoryLabels[item]}</option>)}
            </select>
            <select className="field" onChange={(event) => setZoneId(event.target.value)} value={zoneId}>
              <option value="">{t("visitLevel")}</option>
              {showing.zones.map((zone) => <option key={zone.id} value={zone.id}>{zoneLabels[zone.zone_type]}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <Button disabled={update.isPending} onClick={() => update.mutate()} size="sm"><Save /> {t("save")}</Button>
            <Button onClick={() => setEditing(false)} size="sm" variant="ghost">{t("cancel")}</Button>
          </div>
        </div>
      ) : (
        <p className="text-sm leading-6 text-stone-700">{observation.content}</p>
      )}
      {!editing && (
        <div className="mt-4 flex flex-wrap gap-2">
          {observation.source_transcript_segment_id && (
            <Button onClick={() => onEvidence(observation)} size="sm" variant="outline"><Link2 /> {t("evidence")}</Button>
          )}
          {!readOnly && observation.review_status !== "dismissed" && (
            <>
              <Button onClick={() => setEditing(true)} size="sm" variant="ghost"><Pencil /> {t("edit")}</Button>
              {observation.review_status === "pending" && <Button disabled={review.isPending} onClick={() => review.mutate("confirm")} size="sm" variant="ghost"><Check /> {t("confirm")}</Button>}
              <Button disabled={review.isPending} onClick={() => review.mutate("dismiss")} size="sm" variant="destructive"><Trash2 /> {t("dismiss")}</Button>
            </>
          )}
        </div>
      )}
    </article>
  );
}

function ObservationsTab({
  showing,
  categories,
  categoryLabels,
  zoneLabels,
  onEvidence,
}: {
  showing: ShowingDetail;
  categories: string[];
  categoryLabels: Record<string, string>;
  zoneLabels: Record<string, string>;
  onEvidence: (observation: Observation) => void;
}) {
  const t = useTranslations("Observations");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [category, setCategory] = useState(categories[0] ?? "");
  const [zoneId, setZoneId] = useState("");
  const add = useMutation({
    mutationFn: () => api.observations.create({ visit_id: showing.id, content, category, zone_id: zoneId || null }),
    onSuccess: () => {
      setContent("");
      toast.success(t("added"));
      queryClient.invalidateQueries({ queryKey: ["showing", showing.id] });
    },
    onError: (error) => toast.error(error.message),
  });
  useEffect(() => {
    if (!category && categories[0]) setCategory(categories[0]);
  }, [categories, category]);
  const groups = useMemo(() => {
    const result = new Map<string, Observation[]>();
    showing.observations.forEach((item) => {
      const key = item.zone_id ?? "visit";
      result.set(key, [...(result.get(key) ?? []), item]);
    });
    return [...result.entries()];
  }, [showing.observations]);

  return (
    <div className="space-y-7">
      {showing.status === "draft" && (
        <form className="panel p-5" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
          <h3 className="font-serif text-xl font-semibold">{t("addTitle")}</h3>
          <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_180px_180px_auto]">
            <input className="field" onChange={(event) => setContent(event.target.value)} placeholder={t("contentPlaceholder")} required value={content} />
            <select className="field" disabled={!categories.length} onChange={(event) => setCategory(event.target.value)} value={category}>
              {categories.map((item) => <option key={item} value={item}>{categoryLabels[item]}</option>)}
            </select>
            <select className="field" onChange={(event) => setZoneId(event.target.value)} value={zoneId}>
              <option value="">{t("visitLevel")}</option>
              {showing.zones.map((zone) => <option key={zone.id} value={zone.id}>{zoneLabels[zone.zone_type]}</option>)}
            </select>
            <Button disabled={add.isPending || !categories.length} type="submit"><Plus /> {t("add")}</Button>
          </div>
        </form>
      )}
      {groups.map(([zoneIdKey, items]) => {
        const zone = showing.zones.find((item) => item.id === zoneIdKey);
        return (
          <section key={zoneIdKey}>
            <div className="mb-3 flex items-center gap-2">
              <h3 className="font-serif text-xl font-semibold">{zone ? zoneLabels[zone.zone_type] : t("visitLevel")}</h3>
              <span className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-semibold">{items.length}</span>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              {items.map((observation) => <ObservationCard categories={categories} categoryLabels={categoryLabels} key={observation.id} observation={observation} onEvidence={onEvidence} showing={showing} zoneLabels={zoneLabels} />)}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function TranscriptTab({
  showing,
  targetSegmentId,
  audioUrl,
  audioRef,
}: {
  showing: ShowingDetail;
  targetSegmentId: string | null;
  audioUrl?: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}) {
  const t = useTranslations("Transcript");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [text, setText] = useState("");
  const update = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => api.transcript.update(id, value),
    onSuccess: () => {
      setEditing(null);
      toast.success(t("updated"));
      queryClient.invalidateQueries({ queryKey: ["showing", showing.id] });
    },
    onError: (error) => toast.error(error.message),
  });
  const play = (segmentId: string, start: number | null) => {
    document.getElementById(`segment-${segmentId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (audioRef.current && start !== null) {
      audioRef.current.currentTime = start / 1000;
      void audioRef.current.play();
    }
  };
  // A tag that resolved to nothing has no evidence to jump to, so it is not
  // offered as a jump point.
  const bookmarks = showing.markers.filter((marker) => marker.transcript_segment_id !== null);
  useEffect(() => {
    const segment = showing.transcript.find((item) => item.id === targetSegmentId);
    if (segment) window.setTimeout(() => play(segment.id, segment.timestamp_start), 100);
    // play is intentionally driven only by a new deep-link target.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetSegmentId]);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-2">
        {bookmarks.length > 0 && (
          <div className="panel p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-400">{t("voiceTags")}</p>
            <div className="flex flex-wrap gap-2">
              {bookmarks.map((bookmark, index) => (
                <button
                  className="rounded-full border border-stone-200 px-3 py-1.5 text-sm font-semibold text-[#1f6f5b] transition hover:bg-emerald-50"
                  key={bookmark.id}
                  onClick={() => play(bookmark.transcript_segment_id!, bookmark.timestamp_offset_ms)}
                  type="button"
                >
                  {t("voiceTagLabel", { index: index + 1, time: new Date(bookmark.timestamp_offset_ms).toISOString().slice(14, 19) })}
                </button>
              ))}
            </div>
          </div>
        )}
        {showing.transcript.map((segment) => (
          <article className={cn("panel scroll-mt-28 p-4 transition", segment.id === targetSegmentId && "border-emerald-500 ring-4 ring-emerald-500/10")} id={`segment-${segment.id}`} key={segment.id}>
            <div className="flex gap-3">
              <button aria-label={t("playSegment")} className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[#1f6f5b] hover:bg-emerald-100" disabled={!audioUrl} onClick={() => play(segment.id, segment.timestamp_start)} type="button"><Play className="ml-0.5 size-4" /></button>
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex items-center justify-between gap-3 text-xs text-stone-400">
                  <span>{segment.timestamp_start === null ? t("unknownTime") : new Date(segment.timestamp_start).toISOString().slice(14, 19)}</span>
                  {showing.status === "draft" && editing !== segment.id && <button className="font-semibold text-[#1f6f5b]" onClick={() => { setEditing(segment.id); setText(segment.text); }} type="button">{t("correct")}</button>}
                </div>
                {editing === segment.id ? (
                  <div>
                    <textarea className="field-area" onChange={(event) => setText(event.target.value)} value={text} />
                    <div className="mt-2 flex gap-2">
                      <Button disabled={update.isPending} onClick={() => update.mutate({ id: segment.id, value: text })} size="sm"><Save /> {t("save")}</Button>
                      <Button onClick={() => setEditing(null)} size="sm" variant="ghost">{t("cancel")}</Button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-stone-700">{segment.text}</p>
                )}
                {segment.original_text && <p className="mt-2 border-l-2 pl-3 text-xs leading-5 text-stone-400">{t("original")}: {segment.original_text}</p>}
              </div>
            </div>
          </article>
        ))}
      </div>
      <aside className="xl:sticky xl:top-8 xl:self-start">
        <div className="panel p-4">
          <p className="mb-3 text-sm font-semibold">{t("audioTitle")}</p>
          {audioUrl ? <audio className="w-full" controls ref={audioRef} src={audioUrl} /> : <p className="text-sm text-stone-500">{t("audioUnavailable")}</p>}
          <p className="mt-3 text-xs leading-5 text-stone-400">{t("audioHint")}</p>
        </div>
      </aside>
    </div>
  );
}

export function DeliveryPanel({ showing }: { showing: ShowingDetail }) {
  const t = useTranslations("Delivery");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState(showing.contact?.email ?? "");
  const [now, setNow] = useState(() => Date.now());
  const [createdLinkUrl, setCreatedLinkUrl] = useState<string | null>(null);
  const delivery = useQuery({
    queryKey: ["delivery", showing.id],
    queryFn: () => api.showings.delivery(showing.id),
  });

  useEffect(() => {
    const links = delivery.data?.share_links ?? [];
    const nextExpiry = links.reduce<number | null>((soonest, link) => {
      if (link.revoked || link.expires_at === null) return soonest;
      const expiresAt = new Date(link.expires_at).getTime();
      if (!Number.isFinite(expiresAt) || expiresAt <= now) return soonest;
      return soonest === null ? expiresAt : Math.min(soonest, expiresAt);
    }, null);
    if (nextExpiry === null) return;

    const delay = Math.max(
      1,
      Math.min(nextExpiry - now, MAX_EXPIRY_TIMER_MS),
    );
    const timer = window.setTimeout(() => setNow(Date.now()), delay);
    return () => window.clearTimeout(timer);
  }, [delivery.data?.share_links, now]);

  const refreshDelivery = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["showing", showing.id] }),
      queryClient.invalidateQueries({ queryKey: ["delivery", showing.id] }),
      queryClient.invalidateQueries({ queryKey: ["showings"] }),
    ]);
  };

  const copyLink = async (url: string) => {
    let copied = false;
    try {
      copied = await copyTextToClipboard(url);
    } catch {
      copied = false;
    }
    if (copied) {
      toast.success(t("linkCopied"));
    } else {
      toast.error(t("linkCopyFailed"));
    }
    return copied;
  };

  const handleCreatedLink = (url: string) => {
    setCreatedLinkUrl(url);
    toast.success(t("linkCreated"));
    void refreshDelivery().catch(() => undefined);
  };

  const link = useMutation({
    mutationFn: () => api.showings.send(showing.id, { channel: "link_only" }),
    onSuccess: (item) => handleCreatedLink(item.share_url),
    onError: (error) => {
      const payload = error instanceof ApiError ? error.payload as { code?: string } : null;
      toast.error(payload?.code === "subscription_required" ? t("subscriptionRequired") : error.message);
    },
  });
  const replacementLink = useMutation({
    mutationFn: () => api.showings.createShareLink(showing.id),
    onSuccess: (item) => handleCreatedLink(item.url),
    onError: (error) => {
      const payload = error instanceof ApiError ? error.payload as { code?: string } : null;
      toast.error(payload?.code === "subscription_required" ? t("subscriptionRequired") : error.message);
    },
  });
  const revoke = useMutation({
    mutationFn: (linkId: string) => api.showings.revokeShareLink(showing.id, linkId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["delivery", showing.id] });
      setCreatedLinkUrl(null);
      toast.success(t("linkRevoked"));
    },
    onError: (error) => toast.error(error.message),
  });
  const send = useMutation({
    mutationFn: () => api.showings.send(showing.id, { channel: "email", to_email: email }),
    onSuccess: async () => {
      toast.success(t("emailSent"));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["showing", showing.id] }),
        queryClient.invalidateQueries({ queryKey: ["delivery", showing.id] }),
        queryClient.invalidateQueries({ queryKey: ["showings"] }),
      ]);
    },
    onError: async (error) => {
      await queryClient.invalidateQueries({ queryKey: ["delivery", showing.id] });
      const payload = error instanceof ApiError ? error.payload as { code?: string } : null;
      toast.error(
        payload?.code === "subscription_required"
          ? t("subscriptionRequired")
          : payload?.code === "email_delivery_outcome_unknown"
            ? t("emailOutcomeUnknown")
            : payload?.code === "email_delivery_in_progress"
              ? t("emailInProgress")
            : error.message,
      );
    },
  });
  const emailDelivery = delivery.data?.sends.find((item) => item.channel === "email");
  const emailRetryBlocked =
    emailDelivery?.status === "pending" || emailDelivery?.status === "outcome_unknown";
  const openCount = delivery.data?.share_links.reduce((total, item) => total + item.open_count, 0) ?? 0;
  const history = [
    ...(delivery.data?.share_links.map((item) => ({ kind: "link" as const, at: item.created_at, item })) ?? []),
    ...(delivery.data?.sends.map((item) => ({ kind: "send" as const, at: item.sent_at, item })) ?? []),
  ].sort((left, right) => right.at.localeCompare(left.at));
  const activeShareLink = delivery.data?.share_links.find(
    (item) => isActiveShareLink(item, now),
  );
  const activePdfUrl = activeShareLink
    ? getPublicReportPdfUrl(activeShareLink.url)
    : null;
  const canCreateReplacement =
    showing.status === "sent_to_client" && delivery.isSuccess && !activeShareLink;
  const linkPending = link.isPending || replacementLink.isPending;
  return (
    <section className="panel mt-7 overflow-hidden border-emerald-200">
      <div className="border-b bg-emerald-50 p-5 sm:p-6">
        <p className="eyebrow mb-2">{t("eyebrow")}</p>
        <h2 className="font-serif text-2xl font-semibold">{t("title")}</h2>
        <p className="mt-1 text-sm text-stone-600">{t("body")}</p>
      </div>
      <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-2">
        <form className="rounded-xl border p-4" onSubmit={(event) => { event.preventDefault(); send.mutate(); }}>
          <div className="mb-3 flex items-center gap-2 font-semibold"><Mail className="size-4 text-[#1f6f5b]" /> {t("emailTitle")}</div>
          <input className="field" onChange={(event) => setEmail(event.target.value)} placeholder={t("emailPlaceholder")} required type="email" value={email} />
          <Button className="mt-3 w-full" disabled={send.isPending || emailRetryBlocked || showing.status !== "confirmed"} type="submit"><Send /> {t("sendEmail")}</Button>
          {emailDelivery?.status === "outcome_unknown" && <p className="mt-2 text-xs leading-5 text-amber-700">{t("emailOutcomeUnknown")}</p>}
          {emailDelivery?.status === "pending" && <p className="mt-2 text-xs leading-5 text-stone-500">{t("emailInProgress")}</p>}
        </form>
        <div className="rounded-xl border p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold"><Link2 className="size-4 text-[#1f6f5b]" /> {t("linkTitle")}</div>
          <p className="mb-3 text-sm leading-6 text-stone-500">{t("linkBody")}</p>
          {showing.status === "confirmed" && <Button className="w-full" disabled={linkPending} onClick={() => link.mutate()} variant="outline"><Link2 /> {t("copyLink")}</Button>}
          {canCreateReplacement && <Button className="w-full" disabled={linkPending} onClick={() => replacementLink.mutate()} variant="outline"><Link2 /> {t("createReplacementLink")}</Button>}
          {activeShareLink && (
            <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-800">{t("activeLink")}</p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <label className="sr-only" htmlFor={`active-share-link-${activeShareLink.id}`}>{t("manualUrl")}</label>
                <input
                  aria-label={t("manualUrl")}
                  className="field min-w-0 flex-1 bg-white text-xs"
                  id={`active-share-link-${activeShareLink.id}`}
                  onClick={(event) => event.currentTarget.select()}
                  onFocus={(event) => event.currentTarget.select()}
                  readOnly
                  value={activeShareLink.url}
                />
                <Button aria-label={t("copyLinkAction")} disabled={!isActiveShareLink(activeShareLink, Date.now())} onClick={() => { if (isActiveShareLink(activeShareLink, Date.now())) void copyLink(activeShareLink.url); }} variant="outline"><Copy /> {t("copyLinkAction")}</Button>
              </div>
              {activePdfUrl && <a className="mt-3 inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg border border-[#1f6f5b] px-3 text-sm font-semibold text-[#1f6f5b] transition hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-[#1f6f5b]/30" href={activePdfUrl} onClick={(event) => { if (!isActiveShareLink(activeShareLink, Date.now())) event.preventDefault(); }} rel="noreferrer" target="_blank"><FileDown className="size-4" /> {t("openPdf")}</a>}
            </div>
          )}
          {createdLinkUrl && createdLinkUrl !== activeShareLink?.url && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="mb-2 text-xs leading-5 text-amber-900">{t("linkCreated")}</p>
              <label className="sr-only" htmlFor="created-share-link-recovery">{t("manualUrl")}</label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input aria-label={t("manualUrl")} className="field min-w-0 flex-1 bg-white text-xs" id="created-share-link-recovery" onClick={(event) => event.currentTarget.select()} onFocus={(event) => event.currentTarget.select()} readOnly value={createdLinkUrl} />
                <Button aria-label={t("copyLinkAction")} onClick={() => void copyLink(createdLinkUrl)} variant="outline"><Copy /> {t("copyLinkAction")}</Button>
              </div>
            </div>
          )}
          {showing.status === "sent_to_client" && !activeShareLink && <p className="mt-2 text-xs leading-5 text-stone-400">{t("alreadyDelivered")}</p>}
        </div>
      </div>
      <div className="border-t px-5 py-4 sm:px-6">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t("history")}</h3>
          <span className="text-xs text-stone-400">{t("opens", { count: openCount })}</span>
        </div>
        {delivery.isLoading ? <p className="text-sm text-stone-400">{t("loadingHistory")}</p> : delivery.isError ? <p className="text-sm text-red-700">{t("historyError")}</p> : history.length === 0 ? <p className="text-sm text-stone-400">{t("noHistory")}</p> : history.map((entry, index) => (
          <div className="flex items-center justify-between gap-3 border-t py-2 text-sm first:border-0" key={`${entry.kind}-${entry.at}-${index}`}>
            <div>
              <span>{entry.kind === "send" ? entry.item.channel === "email" ? entry.item.status === "outcome_unknown" ? t("emailOutcomeUnknown") : entry.item.status === "failed" ? t("emailFailed") : entry.item.status === "pending" ? t("emailInProgress") : t("sentTo", { email: entry.item.to_email ?? "" }) : t("linkDelivered") : t("linkCreatedWithOpens", { count: entry.item.open_count })}</span>
              {entry.kind === "link" && <span className={cn("ml-2 rounded-full px-2 py-0.5 text-xs", shareLinkStatus(entry.item, now) === "active" ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-500")}>{t(shareLinkStatus(entry.item, now))}</span>}
              <span className="ml-2 text-xs text-stone-400">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.at))}</span>
            </div>
            {entry.kind === "link" && (
              <div className="flex flex-wrap items-center justify-end gap-2">
                {isActiveShareLink(entry.item, now) && <>
                  <label className="sr-only" htmlFor={`history-share-link-${entry.item.id}`}>{t("manualUrl")}</label>
                  <input aria-label={t("manualUrl")} className="field h-8 w-48 bg-white text-xs" id={`history-share-link-${entry.item.id}`} onClick={(event) => event.currentTarget.select()} onFocus={(event) => event.currentTarget.select()} readOnly value={entry.item.url} />
                  <Button aria-label={t("copyLinkAction")} disabled={revoke.isPending} onClick={() => { if (isActiveShareLink(entry.item, Date.now())) void copyLink(entry.item.url); }} size="sm" variant="outline"><Copy /> {t("copyLinkAction")}</Button>
                  <Button aria-label={t("revokeLink")} disabled={revoke.isPending} onClick={() => { if (isActiveShareLink(entry.item, Date.now()) && window.confirm(t("revokeConfirm"))) revoke.mutate(entry.item.id); }} size="sm" variant="destructive"><Trash2 /> {t("revokeLink")}</Button>
                  <a aria-label={t("openLink")} className="text-[#1f6f5b]" href={entry.item.url} onClick={(event) => { if (!isActiveShareLink(entry.item, Date.now())) event.preventDefault(); }} rel="noreferrer" target="_blank"><ExternalLink className="size-4" /></a>
                </>}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function AttachPropertyPanel({
  showing,
  onAttached,
}: {
  showing: ShowingDetail;
  onAttached: () => void;
}) {
  const t = useTranslations("Showing");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState("");
  const [address, setAddress] = useState("");
  const properties = useQuery({ queryKey: ["properties"], queryFn: api.properties.list });
  const attach = useMutation({
    mutationFn: () =>
      subjectId
        ? api.showings.attachProperty(showing.id, { subject_id: subjectId })
        : api.showings.attachProperty(showing.id, { address: address.trim() }),
    onSuccess: (updated) => {
      queryClient.setQueryData<ShowingDetail>(["showing", showing.id], (current) =>
        current ? { ...current, property: updated.property, updated_at: updated.updated_at } : current,
      );
      onAttached();
      toast.success(t("propertyAttached"));
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <section className="mb-6 rounded-2xl border border-amber-300 bg-amber-50 p-5" data-testid="attach-property-panel">
      <div className="mb-4 flex items-start gap-3">
        <div className="rounded-xl bg-amber-100 p-2 text-amber-800"><Building2 className="size-5" /></div>
        <div>
          <h2 className="font-serif text-xl font-semibold">{t("attachPropertyTitle")}</h2>
          <p className="mt-1 text-sm text-stone-600">{t("attachPropertyBody")}</p>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] lg:items-end">
        <label>
          <span className="mb-1.5 block text-xs font-semibold text-stone-600">{t("existingProperty")}</span>
          <select className="field" onChange={(event) => { setSubjectId(event.target.value); if (event.target.value) setAddress(""); }} value={subjectId}>
            <option value="">{t("chooseProperty")}</option>
            {properties.data?.map((property) => <option key={property.id} value={property.id}>{property.display_name} · {property.address}</option>)}
          </select>
        </label>
        <span className="pb-3 text-center text-xs font-semibold uppercase tracking-wide text-stone-400">{t("orAddress")}</span>
        <label>
          <span className="mb-1.5 block text-xs font-semibold text-stone-600">{t("orAddress")}</span>
          <input className="field" onChange={(event) => { setAddress(event.target.value); if (event.target.value) setSubjectId(""); }} placeholder={t("addressPlaceholder")} value={address} />
        </label>
        <Button disabled={attach.isPending || (!subjectId && !address.trim())} onClick={() => attach.mutate()}><Building2 /> {t("attach")}</Button>
      </div>
    </section>
  );
}

export function ShowingWorkspace({ id }: { id: string }) {
  const t = useTranslations("Showing");
  const reportT = useTranslations("ReportEditor");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("report");
  const [reportContent, setReportContent] = useState<ReportContent | null>(null);
  const [loadedReportId, setLoadedReportId] = useState<string | null>(null);
  const [targetSegmentId, setTargetSegmentId] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const detail = useQuery({
    queryKey: ["showing", id],
    queryFn: () => api.showings.get(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && !["ready", "failed", "not_started"].includes(data.processing_status) ? 3000 : false;
    },
  });
  const vertical = useQuery({ queryKey: ["vertical", "real_estate"], queryFn: api.vertical });
  const audio = detail.data?.media.find((item) => item.type === "audio");
  const audioDownload = useQuery({
    queryKey: ["media", id, audio?.id],
    queryFn: () => api.showings.mediaDownload(id, audio!.id),
    enabled: Boolean(audio),
    staleTime: 10 * 60_000,
  });

  useEffect(() => {
    if (detail.data?.report && detail.data.report.id !== loadedReportId) {
      setReportContent(detail.data.report.content);
      setLoadedReportId(detail.data.report.id);
    }
  }, [detail.data?.report, loadedReportId]);

  const showing = detail.data;
  const categories = vertical.data?.observation_schema ?? [];
  const categoryLabels = vertical.data?.display_labels.observations ?? {};
  const zoneLabels = vertical.data?.display_labels.zones ?? {};
  const pendingSensitive = showing?.observations.filter((item) => item.flags.sensitive === true && item.review_status === "pending") ?? [];
  const reviewed = showing?.observations.some((item) => ["confirmed", "edited"].includes(item.review_status)) ?? false;
  const confirmReasons = [
    ...(!showing?.property ? [reportT("guardProperty")] : []),
    ...(!reviewed ? [reportT("guardReview")] : []),
    ...(pendingSensitive.length ? [reportT("guardSensitive", { count: pendingSensitive.length })] : []),
    ...(confirmError ? [confirmError] : []),
  ];

  const saveReport = useMutation({
    mutationFn: async () => {
      if (!showing?.report || !reportContent) throw new Error(reportT("missingReport"));
      return api.reports.update(showing.report.id, reportContent);
    },
    onSuccess: (report) => {
      queryClient.setQueryData<ShowingDetail>(["showing", id], (current) => current ? { ...current, report } : current);
      toast.success(reportT("saved"));
    },
    onError: (error) => toast.error(error.message),
  });
  const confirm = useMutation({
    mutationFn: async () => {
      if (showing?.report && reportContent) await api.reports.update(showing.report.id, reportContent);
      return api.showings.confirm(id);
    },
    onSuccess: () => {
      setConfirmError("");
      toast.success(reportT("confirmed"));
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["showing", id] }),
        queryClient.invalidateQueries({ queryKey: ["showings"] }),
      ]);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 422) {
        const payload = error.payload as { code?: string; detail?: string; offending_observation_ids?: string[] };
        setConfirmError(payload.code === "property_required" ? reportT("guardProperty") : payload.detail ?? error.message);
      }
      toast.error(error.message);
    },
  });
  const applyRewrite = async (observation: Observation, rewrite: string) => {
    try {
      const updated = await api.observations.update(observation.id, { content: rewrite });
      queryClient.setQueryData<ShowingDetail>(["showing", id], (current) => cacheObservation(current, updated));
      toast.success(reportT("rewriteApplied"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : reportT("rewriteFailed"));
    }
  };
  const showEvidence = (observation: Observation) => {
    if (!observation.source_transcript_segment_id) return;
    setTargetSegmentId(observation.source_transcript_segment_id);
    setTab("transcript");
  };

  if (detail.isLoading || vertical.isLoading) return <LoadingState />;
  if (!showing || detail.isError || !vertical.data || vertical.isError) return <ErrorState retry={() => { detail.refetch(); vertical.refetch(); }} />;
  const photos = showing.media.filter((item) => item.type === "photo");
  const tabs: Array<{ key: Tab; label: string; count?: number }> = [
    { key: "report", label: t("report") },
    { key: "observations", label: t("observations"), count: showing.observations.length },
    { key: "transcript", label: t("transcript"), count: showing.transcript.length },
  ];

  return (
    <div>
      <Link className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-stone-500 hover:text-stone-950" href="/"><ArrowLeft className="size-4" /> {t("back")}</Link>
      <div className="mb-7 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-3"><StatusBadge showing={showing} /><span className="text-xs text-stone-400">{new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(tourDate(showing))}</span></div>
          <h1 className="page-title truncate">{showing.property?.display_name ?? t("unassignedTitle")}</h1>
          <p className="mt-2 text-stone-500">{showing.property?.address ?? t("unassignedBody")}{showing.contact ? ` · ${showing.contact.name}` : ""}</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-stone-500"><Clock3 className="size-4" /> {showing.ended_at ? t("completed") : t("inProgress")}</div>
      </div>

      {!showing.property && showing.status !== "sent_to_client" && <AttachPropertyPanel onAttached={() => setConfirmError("")} showing={showing} />}
      <ProcessingBanner showing={showing} />
      {photos.length > 0 && <section className="mb-6"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><ImageIcon className="size-4" /> {t("photos", { count: photos.length })}</div><div className="flex gap-3 overflow-x-auto pb-2">{photos.map((media) => <div key={media.id}><PhotoThumb mediaId={media.id} visitId={id} /><p className="mt-1 text-xs text-stone-400">{media.timestamp_offset_ms === null ? t("noTimestamp") : `${Math.round(media.timestamp_offset_ms / 1000)}s`}</p></div>)}</div></section>}

      <div className="no-print mb-6 flex gap-1 overflow-x-auto rounded-xl bg-stone-200/70 p-1">
        {tabs.map((item) => <button className={cn("flex min-w-max items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-stone-500 transition", tab === item.key && "bg-white text-stone-950 shadow-sm")} key={item.key} onClick={() => setTab(item.key)} type="button">{item.label}{item.count !== undefined && <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px]">{item.count}</span>}</button>)}
      </div>

      {tab === "report" && (showing.report && reportContent ? (
        <ReportEditor
          confirmDisabled={confirmReasons.length > 0}
          confirmReasons={confirmReasons}
          content={reportContent}
          observations={showing.observations}
          onApplyRewrite={applyRewrite}
          onChange={setReportContent}
          onConfirm={() => confirm.mutate()}
          onEvidence={showEvidence}
          onSave={() => saveReport.mutate()}
          pending={saveReport.isPending || confirm.isPending}
          readOnly={showing.status !== "draft"}
          zoneLabels={zoneLabels}
        />
      ) : <div className="panel flex min-h-64 flex-col items-center justify-center p-8 text-center"><CircleDot className="mb-3 size-7 text-stone-300" /><h2 className="font-serif text-xl font-semibold">{t("reportPendingTitle")}</h2><p className="mt-2 text-sm text-stone-500">{t("reportPendingBody")}</p></div>)}
      {tab === "observations" && <ObservationsTab categories={categories} categoryLabels={categoryLabels} onEvidence={showEvidence} showing={showing} zoneLabels={zoneLabels} />}
      {tab === "transcript" && <TranscriptTab audioRef={audioRef} audioUrl={audioDownload.data?.download_url} showing={showing} targetSegmentId={targetSegmentId} />}
      {["confirmed", "sent_to_client"].includes(showing.status) && <DeliveryPanel showing={showing} />}
    </div>
  );
}
