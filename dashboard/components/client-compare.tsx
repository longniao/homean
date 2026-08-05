"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { CompareTable } from "@/components/compare-table";
import { ErrorState, LoadingState } from "@/components/page-state";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function ClientCompare({ id }: { id: string }) {
  const t = useTranslations("Compare");
  const contact = useQuery({ queryKey: ["contact", id], queryFn: () => api.contacts.get(id) });
  const list = useQuery({ queryKey: ["showings", "contact", id], queryFn: () => api.showings.list({ contactId: id }) });
  const details = useQueries({ queries: (list.data?.items ?? []).map((showing) => ({ queryKey: ["showing", showing.id], queryFn: () => api.showings.get(showing.id) })) });
  if (contact.isLoading || list.isLoading || details.some((query) => query.isLoading)) return <LoadingState />;
  if (!contact.data || list.isError || details.some((query) => query.isError)) return <ErrorState />;
  const showings = details.flatMap((query) => query.data ? [query.data] : []);
  return <div><div className="no-print mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><Link className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-stone-500" href={`/clients/${id}`}><ArrowLeft className="size-4" /> {t("back")}</Link><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{t("title", { name: contact.data.name })}</h1><p className="mt-3 text-stone-500">{t("subtitle", { count: showings.length })}</p></div><Button onClick={() => window.print()} variant="outline"><Printer /> {t("print")}</Button></div><CompareTable showings={showings} /></div>;
}
