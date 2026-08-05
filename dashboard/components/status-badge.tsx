"use client";

import { useTranslations } from "next-intl";

import type { Showing } from "@/lib/api";
import { cn } from "@/lib/utils";

export function StatusBadge({ showing }: { showing: Showing }) {
  const t = useTranslations("Status");
  const processing = !["ready", "failed", "not_started"].includes(
    showing.processing_status,
  );
  const key = processing ? "processing" : showing.status;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
        key === "processing" && "bg-amber-100 text-amber-800",
        key === "draft" && "bg-stone-200 text-stone-700",
        key === "confirmed" && "bg-emerald-100 text-emerald-800",
        key === "sent_to_client" && "bg-blue-100 text-blue-800",
      )}
    >
      {processing && <span className="size-1.5 animate-pulse rounded-full bg-current" />}
      {t(key)}
    </span>
  );
}
