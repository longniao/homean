"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

import type { ShowingDetail, VerticalConfig } from "@/lib/api";

export function CompareTable({ showings, zoneLabels }: { showings: ShowingDetail[]; zoneLabels: VerticalConfig["display_labels"]["zones"] }) {
  const t = useTranslations("Compare");
  const resolveZoneKey = (zoneType: string) => zoneLabels[zoneType] ? zoneType : "other";
  const zoneTypes = Array.from(new Set(showings.flatMap((showing) => showing.zones.map((zone) => resolveZoneKey(zone.zone_type)))));
  const isConfirmed = (showing: ShowingDetail) =>
    ["confirmed", "sent_to_client"].includes(showing.status) && showing.report?.status === "confirmed";
  const bullets = (items: { text: string }[] | undefined): ReactNode => items?.length
    ? <ul className="list-disc space-y-2 pl-4">{items.map((item, index) => <li key={index}>{item.text}</li>)}</ul>
    : <span className="text-muted-foreground">{t("none")}</span>;
  const rows = [
    { key: "summary", label: t("summary"), render: (showing: ShowingDetail) => showing.report?.content.executive_summary || t("none") },
    { key: "highlights", label: t("highlights"), render: (showing: ShowingDetail) => bullets(showing.report?.content.highlights) },
    { key: "concerns", label: t("concerns"), render: (showing: ShowingDetail) => bullets(showing.report?.content.concerns) },
    { key: "followUps", label: t("followUps"), render: (showing: ShowingDetail) => bullets(showing.report?.content.follow_ups) },
    { key: "key", label: t("keyObservations"), render: (showing: ShowingDetail) => bullets(showing.observations.filter((item) => ["confirmed", "edited"].includes(item.review_status)).slice(0, 4).map((item) => ({ text: item.content }))) },
    ...zoneTypes.map((zoneType) => ({
      key: `zone:${zoneType}`,
      label: zoneLabels[zoneType] ?? zoneLabels.other,
      render: (showing: ShowingDetail) => {
        const zoneIds = showing.zones.filter((zone) => resolveZoneKey(zone.zone_type) === zoneType).map((zone) => zone.id);
        return showing.observations.filter((item) => item.zone_id && zoneIds.includes(item.zone_id) && ["confirmed", "edited"].includes(item.review_status)).map((item) => item.content).join(" · ") || t("none");
      },
    })),
  ];
  return (
    <div className="overflow-x-auto rounded-2xl border bg-white">
      <table aria-label={t("tableLabel")} className="min-w-[900px] w-full border-collapse text-left text-sm">
        <thead><tr className="bg-[#ecece4]"><th scope="col" className="sticky left-0 z-10 w-48 bg-[#ecece4] p-4 font-semibold">{t("category")}</th>{showings.map((showing) => <th scope="col" className="min-w-64 border-l p-4" key={showing.id}><span className="block font-serif text-lg font-semibold">{showing.property?.display_name ?? t("unassignedProperty")}</span><span className="mt-1 block text-xs font-normal text-stone-500">{showing.property?.address ?? t("unassignedProperty")}</span><span className="mt-3 block text-xs font-normal text-muted-foreground">{isConfirmed(showing) ? t("confirmed") : t("awaitingReview")}</span><Link className="no-print mt-2 inline-block text-xs underline underline-offset-4" href={`/showings/${showing.id}`}>{isConfirmed(showing) ? t("viewShowing") : t("reviewShowing")}</Link></th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr className="border-t align-top" key={row.key}><th scope="row" className="sticky left-0 bg-white p-4 font-semibold">{row.label}</th>{showings.map((showing) => <td className="border-l p-4 leading-6 text-stone-600" key={showing.id}>{isConfirmed(showing) ? row.render(showing) : <span className="text-muted-foreground">{t("notConfirmed")}</span>}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
