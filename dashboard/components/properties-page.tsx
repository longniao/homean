"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BedDouble, Building2, MoreHorizontal, Plus, Ruler, Search, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { api, type Property } from "@/lib/api";

export function PropertiesPage() {
  const t = useTranslations("Properties");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Property | null>(null);
  const properties = useQuery({ queryKey: ["properties"], queryFn: api.properties.list });
  const save = useMutation({
    mutationFn: (body: { display_name: string; address: string; attributes: Record<string, unknown> }) => editing ? api.properties.update(editing.id, body) : api.properties.create(body),
    onSuccess: () => {
      toast.success(editing ? t("updated") : t("created"));
      setFormOpen(false); setEditing(null);
      queryClient.invalidateQueries({ queryKey: ["properties"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({ mutationFn: api.properties.remove, onSuccess: () => { toast.success(t("deleted")); queryClient.invalidateQueries({ queryKey: ["properties"] }); }, onError: (error) => toast.error(error.message) });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const numeric = (key: string) => data.get(key) ? Number(data.get(key)) : null;
    save.mutate({
      display_name: String(data.get("display_name")),
      address: String(data.get("address")),
      attributes: { beds: numeric("beds"), baths: numeric("baths"), sqft: numeric("sqft"), listing_price: numeric("listing_price"), mls_id: String(data.get("mls_id")) || null },
    });
  };
  const visible = properties.data?.filter((property) => `${property.display_name} ${property.address}`.toLowerCase().includes(query.toLowerCase()));
  return <div>
    <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{t("title")}</h1><p className="mt-3 text-stone-500">{t("subtitle")}</p></div><Button onClick={() => { setEditing(null); setFormOpen(true); }}><Plus /> {t("addProperty")}</Button></div>
    {formOpen && <form className="panel mb-6 p-5" key={editing?.id ?? "new"} onSubmit={submit}><div className="mb-4 flex justify-between"><h2 className="font-serif text-xl font-semibold">{editing ? t("editTitle") : t("addTitle")}</h2><Button onClick={() => setFormOpen(false)} size="sm" variant="ghost">{t("cancel")}</Button></div><div className="grid gap-3 md:grid-cols-2"><input className="field" defaultValue={editing?.display_name} name="display_name" placeholder={t("displayName")} required /><input className="field" defaultValue={editing?.address} name="address" placeholder={t("address")} required /><input className="field" defaultValue={editing?.attributes.beds ?? ""} min="0" name="beds" placeholder={t("beds")} type="number" /><input className="field" defaultValue={editing?.attributes.baths ?? ""} min="0" name="baths" placeholder={t("baths")} step="0.5" type="number" /><input className="field" defaultValue={editing?.attributes.sqft ?? ""} min="0" name="sqft" placeholder={t("sqft")} type="number" /><input className="field" defaultValue={editing?.attributes.listing_price ?? ""} min="0" name="listing_price" placeholder={t("price")} type="number" /><input className="field md:col-span-2" defaultValue={editing?.attributes.mls_id ?? ""} name="mls_id" placeholder={t("mls")} /></div><Button className="mt-4" disabled={save.isPending} type="submit">{t("save")}</Button></form>}
    <label className="relative mb-5 block max-w-lg"><span className="sr-only">{t("search")}</span><Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(e) => setQuery(e.target.value)} placeholder={t("searchPlaceholder")} value={query} /></label>
    {properties.isLoading ? <LoadingState /> : properties.isError ? <ErrorState retry={() => properties.refetch()} /> : visible?.length ? <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">{visible.map((property) => <article className="panel overflow-hidden" key={property.id}><div className="flex h-28 items-end bg-gradient-to-br from-[#dfe9e3] to-[#efeadf] p-5"><Building2 className="size-8 text-[#1f6f5b]" /></div><div className="p-5"><Link className="font-serif text-xl font-semibold hover:text-[#1f6f5b]" href={`/properties/${property.id}`}>{property.display_name}</Link><p className="mt-1 text-sm text-stone-500">{property.address}</p><div className="mt-4 flex gap-4 text-xs text-stone-500">{property.attributes.beds !== null && property.attributes.beds !== undefined && <span className="flex items-center gap-1"><BedDouble className="size-3.5" /> {t("bedsCount", { count: property.attributes.beds })}</span>}{property.attributes.sqft && <span className="flex items-center gap-1"><Ruler className="size-3.5" /> {t("sqftCount", { count: property.attributes.sqft })}</span>}</div><div className="mt-5 flex items-center justify-between border-t pt-3"><Link className="text-sm font-semibold text-[#1f6f5b]" href={`/properties/${property.id}`}>{t("visitHistory")}</Link><div className="flex"><Button aria-label={t("edit")} onClick={() => { setEditing(property); setFormOpen(true); }} size="icon-sm" variant="ghost"><MoreHorizontal /></Button><Button aria-label={t("delete")} onClick={() => window.confirm(t("deleteConfirm")) && remove.mutate(property.id)} size="icon-sm" variant="destructive"><Trash2 /></Button></div></div></div></article>)}</div> : <div className="panel flex min-h-72 flex-col items-center justify-center p-8 text-center"><Building2 className="mb-4 size-8 text-stone-300" /><h2 className="font-serif text-2xl font-semibold">{t("emptyTitle")}</h2><p className="mt-2 text-sm text-stone-500">{t("emptyBody")}</p></div>}
  </div>;
}
