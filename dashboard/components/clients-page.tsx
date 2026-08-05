"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, MoreHorizontal, Phone, Plus, Search, Trash2, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { api, type Contact } from "@/lib/api";

export function ClientsPage() {
  const t = useTranslations("Clients");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Contact | null>(null);
  const contacts = useQuery({ queryKey: ["contacts"], queryFn: api.contacts.list });
  const save = useMutation({
    mutationFn: (body: Pick<Contact, "name" | "email" | "phone" | "notes">) =>
      editing ? api.contacts.update(editing.id, body) : api.contacts.create(body),
    onSuccess: () => {
      toast.success(editing ? t("updated") : t("created"));
      setFormOpen(false);
      setEditing(null);
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: api.contacts.remove,
    onSuccess: () => {
      toast.success(t("deleted"));
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save.mutate({
      name: String(data.get("name")),
      email: String(data.get("email")) || null,
      phone: String(data.get("phone")) || null,
      notes: String(data.get("notes")) || null,
    });
  };
  const visible = contacts.data?.filter((contact) =>
    `${contact.name} ${contact.email ?? ""} ${contact.phone ?? ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );

  return (
    <div>
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{t("title")}</h1><p className="mt-3 text-stone-500">{t("subtitle")}</p></div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }}><Plus /> {t("addClient")}</Button>
      </div>
      {formOpen && (
        <form className="panel mb-6 p-5" key={editing?.id ?? "new"} onSubmit={submit}>
          <div className="mb-4 flex items-center justify-between"><h2 className="font-serif text-xl font-semibold">{editing ? t("editTitle") : t("addTitle")}</h2><Button onClick={() => setFormOpen(false)} size="sm" variant="ghost">{t("cancel")}</Button></div>
          <div className="grid gap-3 md:grid-cols-2">
            <input className="field" defaultValue={editing?.name} name="name" placeholder={t("name")} required />
            <input className="field" defaultValue={editing?.email ?? ""} name="email" placeholder={t("email")} type="email" />
            <input className="field" defaultValue={editing?.phone ?? ""} name="phone" placeholder={t("phone")} />
            <input className="field" defaultValue={editing?.notes ?? ""} name="notes" placeholder={t("notes")} />
          </div>
          <Button className="mt-4" disabled={save.isPending} type="submit">{t("save")}</Button>
        </form>
      )}
      <label className="relative mb-5 block max-w-lg"><span className="sr-only">{t("search")}</span><Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(event) => setQuery(event.target.value)} placeholder={t("searchPlaceholder")} value={query} /></label>
      {contacts.isLoading ? <LoadingState /> : contacts.isError ? <ErrorState retry={() => contacts.refetch()} /> : visible?.length ? (
        <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">{visible.map((contact) => (
          <article className="panel p-5" key={contact.id}>
            <div className="flex gap-4"><div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[#1f6f5b]"><UserRound className="size-5" /></div><div className="min-w-0 flex-1"><Link className="font-serif text-xl font-semibold hover:text-[#1f6f5b]" href={`/clients/${contact.id}`}>{contact.name}</Link><div className="mt-2 space-y-1 text-sm text-stone-500">{contact.email && <p className="flex items-center gap-2 truncate"><Mail className="size-3.5" /> {contact.email}</p>}{contact.phone && <p className="flex items-center gap-2"><Phone className="size-3.5" /> {contact.phone}</p>}{!contact.email && !contact.phone && <p>{t("noContactInfo")}</p>}</div></div></div>
            <div className="mt-5 flex items-center justify-between border-t pt-3"><Link className="text-sm font-semibold text-[#1f6f5b]" href={`/clients/${contact.id}`}>{t("viewHistory")}</Link><div className="flex"><Button aria-label={t("edit")} onClick={() => { setEditing(contact); setFormOpen(true); }} size="icon-sm" variant="ghost"><MoreHorizontal /></Button><Button aria-label={t("delete")} onClick={() => window.confirm(t("deleteConfirm")) && remove.mutate(contact.id)} size="icon-sm" variant="destructive"><Trash2 /></Button></div></div>
          </article>
        ))}</div>
      ) : <div className="panel flex min-h-72 flex-col items-center justify-center p-8 text-center"><UserRound className="mb-4 size-8 text-stone-300" /><h2 className="font-serif text-2xl font-semibold">{t("emptyTitle")}</h2><p className="mt-2 text-sm text-stone-500">{t("emptyBody")}</p></div>}
    </div>
  );
}
