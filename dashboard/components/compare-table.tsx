"use client";

import { useTranslations } from "next-intl";

import type { ShowingDetail } from "@/lib/api";

export function CompareTable({ showings }: { showings: ShowingDetail[] }) {
  const t = useTranslations("Compare");
  const zoneTypes = Array.from(new Set(showings.flatMap((showing) => showing.zones.map((zone) => zone.zone_type))));
  const rows = [
    { key: "highlights", label: t("highlights"), render: (showing: ShowingDetail) => String(showing.report?.content.highlights.length ?? 0) },
    { key: "concerns", label: t("concerns"), render: (showing: ShowingDetail) => String(showing.report?.content.concerns.length ?? 0) },
    { key: "key", label: t("keyObservations"), render: (showing: ShowingDetail) => showing.observations.filter((item) => item.review_status !== "dismissed").slice(0, 4).map((item) => item.content).join(" · ") || t("none") },
    ...zoneTypes.map((zoneType) => ({
      key: zoneType,
      label: zoneType.replaceAll("_", " "),
      render: (showing: ShowingDetail) => {
        const zoneIds = showing.zones.filter((zone) => zone.zone_type === zoneType).map((zone) => zone.id);
        return showing.observations.filter((item) => item.zone_id && zoneIds.includes(item.zone_id) && item.review_status !== "dismissed").map((item) => item.content).join(" · ") || t("none");
      },
    })),
  ];
  return (
    <div className="overflow-x-auto rounded-2xl border bg-white">
      <table className="min-w-[900px] w-full border-collapse text-left text-sm">
        <thead><tr className="bg-[#ecece4]"><th className="sticky left-0 z-10 w-48 bg-[#ecece4] p-4 font-semibold">{t("category")}</th>{showings.map((showing) => <th className="min-w-64 border-l p-4" key={showing.id}><span className="block font-serif text-lg font-semibold">{showing.property.display_name}</span><span className="mt-1 block text-xs font-normal text-stone-500">{showing.property.address}</span></th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr className="border-t align-top" key={row.key}><th className="sticky left-0 bg-white p-4 font-semibold capitalize">{row.label}</th>{showings.map((showing) => <td className="border-l p-4 leading-6 text-stone-600" key={showing.id}>{row.render(showing)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
