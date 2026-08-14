"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BedDouble, Bath, Ruler } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";
import { tourDate } from "@/lib/tour-date";

export function PropertyDetail({ id }: { id: string }) {
  const t = useTranslations("PropertyDetail");
  const property = useQuery({ queryKey: ["property", id], queryFn: () => api.properties.get(id) });
  const showings = useQuery({ queryKey: ["showings", "property", id], queryFn: () => api.showings.list({ subjectId: id }) });
  if (property.isLoading || showings.isLoading) return <LoadingState />;
  if (!property.data || !showings.data || property.isError || showings.isError) return <ErrorState />;
  return <div><Link className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-stone-500" href="/properties"><ArrowLeft className="size-4" /> {t("back")}</Link><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{property.data.display_name}</h1><p className="mt-2 text-stone-500">{property.data.address}</p><div className="my-7 flex flex-wrap gap-3">{property.data.attributes.beds != null && <span className="rounded-xl bg-white px-3 py-2 text-sm shadow-sm"><BedDouble className="mr-2 inline size-4" />{t("beds", { count: property.data.attributes.beds })}</span>}{property.data.attributes.baths != null && <span className="rounded-xl bg-white px-3 py-2 text-sm shadow-sm"><Bath className="mr-2 inline size-4" />{t("baths", { count: property.data.attributes.baths })}</span>}{property.data.attributes.sqft && <span className="rounded-xl bg-white px-3 py-2 text-sm shadow-sm"><Ruler className="mr-2 inline size-4" />{t("sqft", { count: property.data.attributes.sqft })}</span>}</div><h2 className="mb-4 font-serif text-2xl font-semibold">{t("history", { count: showings.data.items.length })}</h2><div className="space-y-3">{showings.data.items.length ? showings.data.items.map((showing) => <Link className="panel flex items-center justify-between gap-4 p-4" href={`/showings/${showing.id}`} key={showing.id}><div><p className="font-semibold">{showing.contact?.name ?? t("unassigned")}</p><p className="mt-1 text-sm text-stone-500">{new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(tourDate(showing))}</p></div><StatusBadge showing={showing} /></Link>) : <div className="panel p-8 text-center text-sm text-stone-500">{t("empty")}</div>}</div></div>;
}
