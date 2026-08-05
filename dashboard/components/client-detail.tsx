"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows, Mail, Phone } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function ClientDetail({ id }: { id: string }) {
  const t = useTranslations("ClientDetail");
  const contact = useQuery({ queryKey: ["contact", id], queryFn: () => api.contacts.get(id) });
  const showings = useQuery({ queryKey: ["showings", "contact", id], queryFn: () => api.showings.list({ contactId: id }) });
  if (contact.isLoading || showings.isLoading) return <LoadingState />;
  if (!contact.data || !showings.data || contact.isError || showings.isError) return <ErrorState />;
  return (
    <div>
      <Link className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-stone-500" href="/clients"><ArrowLeft className="size-4" /> {t("back")}</Link>
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{contact.data.name}</h1><div className="mt-3 flex flex-wrap gap-4 text-sm text-stone-500">{contact.data.email && <span className="flex items-center gap-2"><Mail className="size-4" /> {contact.data.email}</span>}{contact.data.phone && <span className="flex items-center gap-2"><Phone className="size-4" /> {contact.data.phone}</span>}</div></div>{showings.data.items.length >= 2 && <Button render={<Link href={`/clients/${id}/compare`} />}><GitCompareArrows /> {t("compare")}</Button>}</div>
      <h2 className="mb-4 font-serif text-2xl font-semibold">{t("showings", { count: showings.data.items.length })}</h2>
      <div className="space-y-3">{showings.data.items.length ? showings.data.items.map((showing) => <Link className="panel flex items-center justify-between gap-4 p-4 transition hover:border-stone-300" href={`/showings/${showing.id}`} key={showing.id}><div><p className="font-semibold">{showing.property.display_name}</p><p className="mt-1 text-sm text-stone-500">{showing.property.address} · {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(showing.created_at))}</p></div><StatusBadge showing={showing} /></Link>) : <div className="panel p-8 text-center text-sm text-stone-500">{t("empty")}</div>}</div>
    </div>
  );
}
