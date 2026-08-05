"use client";

import { AlertCircle, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";

export function LoadingState() {
  const t = useTranslations("Common");
  return (
    <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-stone-500">
      <LoaderCircle className="size-5 animate-spin" /> {t("loading")}
    </div>
  );
}

export function ErrorState({ retry }: { retry?: () => void }) {
  const t = useTranslations("Common");
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-stone-300 bg-white/60 p-8 text-center">
      <AlertCircle className="mb-3 size-7 text-red-700" />
      <p className="font-medium">{t("loadError")}</p>
      {retry && (
        <button className="mt-3 text-sm font-semibold text-[#1f6f5b]" onClick={retry}>
          {t("tryAgain")}
        </button>
      )}
    </div>
  );
}
