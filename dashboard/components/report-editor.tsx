"use client";

import { AlertTriangle, Check, GripVertical, Link2, Plus, Save, Sparkles, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { Observation, ReportBullet, ReportContent } from "@/lib/api";
import { cn } from "@/lib/utils";

type EditorProps = {
  content: ReportContent;
  observations: Observation[];
  zoneLabels: Record<string, string>;
  readOnly?: boolean;
  confirmDisabled: boolean;
  confirmReasons: string[];
  pending?: boolean;
  onChange: (content: ReportContent) => void;
  onSave: () => void;
  onConfirm: () => void;
  onEvidence: (observation: Observation) => void;
  onApplyRewrite: (observation: Observation, bulletText: string) => void;
};

type BulletSectionProps = {
  title: string;
  bullets: ReportBullet[];
  observations: Observation[];
  readOnly: boolean;
  onChange: (bullets: ReportBullet[]) => void;
  onEvidence: EditorProps["onEvidence"];
  onApplyRewrite: EditorProps["onApplyRewrite"];
};

function BulletSection({
  title,
  bullets,
  observations,
  readOnly,
  onChange,
  onEvidence,
  onApplyRewrite,
}: BulletSectionProps) {
  const t = useTranslations("ReportEditor");
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const byId = new Map(observations.map((observation) => [observation.id, observation]));
  const move = (target: number) => {
    if (dragIndex === null || dragIndex === target) return;
    const next = [...bullets];
    const [item] = next.splice(dragIndex, 1);
    next.splice(target, 0, item);
    onChange(next);
    setDragIndex(null);
  };
  const add = () => {
    const source = observations[0];
    if (!source) return;
    onChange([...bullets, { text: source.content, observation_ids: [source.id] }]);
  };

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="font-serif text-xl font-semibold">{title}</h3>
        {!readOnly && (
          <Button disabled={observations.length === 0} onClick={add} size="sm" variant="outline">
            <Plus /> {t("addBullet")}
          </Button>
        )}
      </div>
      {bullets.length === 0 ? (
        <p className="rounded-xl bg-stone-50 px-4 py-5 text-sm text-stone-400">{t("emptySection")}</p>
      ) : (
        <div className="space-y-3">
          {bullets.map((bullet, index) => {
            const sources = bullet.observation_ids.map((id) => byId.get(id)).filter(Boolean) as Observation[];
            const sensitive = sources.find((item) => item.flags.sensitive === true);
            const suggestion = sensitive?.flags.suggested_rewrite;
            return (
              <article
                className={cn(
                  "group rounded-xl border bg-stone-50/60 p-3",
                  sensitive && "border-amber-300 bg-amber-50",
                  dragIndex === index && "opacity-50",
                )}
                draggable={!readOnly}
                key={`${bullet.text}-${index}`}
                onDragEnd={() => setDragIndex(null)}
                onDragOver={(event) => event.preventDefault()}
                onDragStart={() => setDragIndex(index)}
                onDrop={() => move(index)}
              >
                <div className="flex gap-2">
                  {!readOnly && <GripVertical className="mt-2 size-4 shrink-0 cursor-grab text-stone-300" />}
                  <div className="min-w-0 flex-1">
                    <textarea
                      aria-label={t("bulletText")}
                      className="min-h-14 w-full resize-y bg-transparent text-sm leading-6 outline-none"
                      onChange={(event) => {
                        const next = [...bullets];
                        next[index] = { ...bullet, text: event.target.value };
                        onChange(next);
                      }}
                      readOnly={readOnly}
                      value={bullet.text}
                    />
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {sources.map((source) => (
                        <button
                          className="inline-flex max-w-full items-center gap-1 rounded-full bg-white px-2 py-1 text-xs font-medium text-[#1f6f5b] shadow-sm hover:underline"
                          key={source.id}
                          onClick={() => onEvidence(source)}
                          type="button"
                        >
                          <Link2 className="size-3" />
                          <span className="truncate">{source.content}</span>
                        </button>
                      ))}
                    </div>
                    {sensitive && (
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-amber-900">
                        <AlertTriangle className="size-4" />
                        <span className="font-semibold">{t("sensitive")}</span>
                        {typeof suggestion === "string" && !readOnly && (
                          <button
                            className="inline-flex items-center gap-1 rounded-lg bg-amber-200/60 px-2 py-1 font-semibold hover:bg-amber-200"
                            onClick={() => onApplyRewrite(sensitive, String(suggestion))}
                            type="button"
                          >
                            <Sparkles className="size-3" /> {t("applyRewrite")}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                  {!readOnly && (
                    <Button
                      aria-label={t("removeBullet")}
                      onClick={() => onChange(bullets.filter((_, itemIndex) => itemIndex !== index))}
                      size="icon-sm"
                      variant="ghost"
                    >
                      <Trash2 />
                    </Button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function ReportEditor({
  content,
  observations,
  zoneLabels,
  readOnly = false,
  confirmDisabled,
  confirmReasons,
  pending,
  onChange,
  onSave,
  onConfirm,
  onEvidence,
  onApplyRewrite,
}: EditorProps) {
  const t = useTranslations("ReportEditor");
  const updateTopLevel = (
    key: "highlights" | "concerns" | "follow_ups",
    bullets: ReportBullet[],
  ) => onChange({ ...content, [key]: bullets });

  return (
    <div className="space-y-5">
      <section className="panel p-5 sm:p-6">
        <label className="block">
          <span className="mb-3 block font-serif text-xl font-semibold">{t("summary")}</span>
          <textarea
            className="field-area min-h-32 text-base leading-7"
            onChange={(event) => onChange({ ...content, executive_summary: event.target.value })}
            readOnly={readOnly}
            value={content.executive_summary}
          />
        </label>
      </section>

      <div className="space-y-4">
        {content.room_by_room.map((room, roomIndex) => {
          const roomObservations = observations.filter((item) => item.zone_id === room.zone_id);
          return (
            <BulletSection
              bullets={room.bullets}
              key={`${room.zone_id ?? "visit"}-${roomIndex}`}
              observations={roomObservations.length ? roomObservations : observations}
              onApplyRewrite={onApplyRewrite}
              onChange={(bullets) => {
                const rooms = [...content.room_by_room];
                rooms[roomIndex] = { ...room, bullets };
                onChange({ ...content, room_by_room: rooms });
              }}
              onEvidence={onEvidence}
              readOnly={readOnly}
              title={room.zone_type ? zoneLabels[room.zone_type] ?? room.zone_type : t("visitLevel")}
            />
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <BulletSection bullets={content.highlights} observations={observations} onApplyRewrite={onApplyRewrite} onChange={(items) => updateTopLevel("highlights", items)} onEvidence={onEvidence} readOnly={readOnly} title={t("highlights")} />
        <BulletSection bullets={content.concerns} observations={observations} onApplyRewrite={onApplyRewrite} onChange={(items) => updateTopLevel("concerns", items)} onEvidence={onEvidence} readOnly={readOnly} title={t("concerns")} />
        <BulletSection bullets={content.follow_ups} observations={observations} onApplyRewrite={onApplyRewrite} onChange={(items) => updateTopLevel("follow_ups", items)} onEvidence={onEvidence} readOnly={readOnly} title={t("followUps")} />
      </div>

      {!readOnly && (
        <div className="sticky bottom-4 z-20 flex flex-col gap-3 rounded-2xl border bg-white/95 p-4 shadow-xl shadow-stone-900/10 backdrop-blur sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            {confirmReasons.length ? (
              <div className="flex items-start gap-2 text-sm text-amber-800" data-testid="confirm-guard">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <span>{confirmReasons.join(" ")}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-emerald-800">
                <Check className="size-4" /> {t("readyToConfirm")}
              </div>
            )}
          </div>
          <Button disabled={pending} onClick={onSave} variant="outline">
            <Save /> {t("saveDraft")}
          </Button>
          <Button data-testid="confirm-button" disabled={confirmDisabled || pending} onClick={onConfirm}>
            <Check /> {t("confirmReport")}
          </Button>
        </div>
      )}
    </div>
  );
}
