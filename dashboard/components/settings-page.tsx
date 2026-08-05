"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ImagePlus, LoaderCircle, Mail, Palette, Phone, Save, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { useToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { api, type Branding } from "@/lib/api";

export function SettingsPage() {
  const t = useTranslations("Settings");
  const toast = useToast();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const branding = useQuery({ queryKey: ["branding"], queryFn: api.branding.get });
  const [draft, setDraft] = useState<Omit<Branding, "id" | "logo_key" | "updated_at"> | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  useEffect(() => {
    if (branding.data && !draft) {
      setDraft({
        display_name: branding.data.display_name,
        phone: branding.data.phone,
        email: branding.data.email,
        license_no: branding.data.license_no,
        accent_color: branding.data.accent_color,
      });
    }
  }, [branding.data, draft]);
  const save = useMutation({
    mutationFn: () => api.branding.update(draft!),
    onSuccess: () => {
      toast.success(t("saved"));
      queryClient.invalidateQueries({ queryKey: ["branding"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const uploadLogo = async (file: File) => {
    setLogoPreview(URL.createObjectURL(file));
    try {
      const presign = await api.branding.presignLogo(file.type);
      const response = await fetch(presign.upload_url, { method: "PUT", headers: presign.headers, body: file });
      if (!response.ok) throw new Error(t("logoFailed"));
      await queryClient.invalidateQueries({ queryKey: ["branding"] });
      toast.success(t("logoUploaded"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("logoFailed"));
    }
  };
  if (me.isLoading || branding.isLoading || !draft) return <LoadingState />;
  if (!me.data || me.isError || branding.isError) return <ErrorState />;
  const update = (key: keyof typeof draft, value: string) => setDraft((current) => current ? { ...current, [key]: value || null } : current);
  const submit = (event: FormEvent) => { event.preventDefault(); save.mutate(); };

  return <div><div className="mb-8"><p className="eyebrow mb-3">{t("eyebrow")}</p><h1 className="page-title">{t("title")}</h1><p className="mt-3 text-stone-500">{t("subtitle")}</p></div><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_440px]">
    <div className="space-y-6">
      <section className="panel p-5 sm:p-6"><div className="mb-5 flex items-center gap-3"><div className="rounded-xl bg-stone-100 p-2 text-stone-600"><UserRound className="size-5" /></div><div><h2 className="font-serif text-xl font-semibold">{t("profileTitle")}</h2><p className="text-sm text-stone-500">{t("profileBody")}</p></div></div><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">{t("name")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.user.name ?? ""} /></label><label className="text-sm font-medium">{t("accountEmail")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.user.email} /></label><label className="text-sm font-medium">{t("workspace")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.workspace.name} /></label><label className="text-sm font-medium">{t("role")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.profile.role.replaceAll("_", " ")} /></label></div><p className="mt-4 text-xs text-stone-400">{t("profileReadOnly")}</p></section>
      <form className="panel p-5 sm:p-6" onSubmit={submit}><div className="mb-5 flex items-center gap-3"><div className="rounded-xl bg-emerald-50 p-2 text-[#1f6f5b]"><Palette className="size-5" /></div><div><h2 className="font-serif text-xl font-semibold">{t("brandingTitle")}</h2><p className="text-sm text-stone-500">{t("brandingBody")}</p></div></div><div className="mb-5 flex items-center gap-4 rounded-xl bg-stone-50 p-4"><div className="flex size-16 items-center justify-center overflow-hidden rounded-xl border bg-white">{logoPreview ? <Image alt={t("logoPreviewAlt")} className="size-full object-contain" height={64} src={logoPreview} unoptimized width={64} /> : <Building2 className="size-6 text-stone-300" />}</div><div><label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-semibold shadow-sm"><ImagePlus className="size-4" /> {t("uploadLogo")}<input accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(event) => event.target.files?.[0] && uploadLogo(event.target.files[0])} type="file" /></label><p className="mt-2 text-xs text-stone-400">{t("logoHint")}</p></div></div><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">{t("displayName")}<input className="field mt-2" onChange={(e) => update("display_name", e.target.value)} value={draft.display_name ?? ""} /></label><label className="text-sm font-medium">{t("license")}<input className="field mt-2" onChange={(e) => update("license_no", e.target.value)} value={draft.license_no ?? ""} /></label><label className="text-sm font-medium">{t("email")}<div className="relative mt-2"><Mail className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(e) => update("email", e.target.value)} type="email" value={draft.email ?? ""} /></div></label><label className="text-sm font-medium">{t("phone")}<div className="relative mt-2"><Phone className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(e) => update("phone", e.target.value)} value={draft.phone ?? ""} /></div></label><label className="text-sm font-medium sm:col-span-2">{t("accent")}<div className="mt-2 flex gap-2"><input aria-label={t("accentPicker")} className="h-11 w-14 rounded-lg border bg-white p-1" onChange={(e) => update("accent_color", e.target.value)} type="color" value={draft.accent_color} /><input className="field" onChange={(e) => update("accent_color", e.target.value)} pattern="^#[0-9A-Fa-f]{6}$" value={draft.accent_color} /></div></label></div><Button className="mt-5" disabled={save.isPending} type="submit">{save.isPending ? <LoaderCircle className="animate-spin" /> : <Save />} {t("saveBranding")}</Button></form>
    </div>
    <aside className="xl:sticky xl:top-8 xl:self-start"><p className="eyebrow mb-3">{t("previewLabel")}</p><div className="overflow-hidden rounded-2xl border bg-white shadow-xl shadow-stone-900/10"><div className="h-2" style={{ background: draft.accent_color }} /><div className="p-7"><div className="mb-8 flex items-start justify-between gap-4"><div>{logoPreview && <Image alt="" className="mb-3 h-10 w-auto max-w-28 object-contain" height={40} src={logoPreview} unoptimized width={112} />}<p className="text-xs font-bold uppercase tracking-[0.15em]" style={{ color: draft.accent_color }}>{t("sampleReport")}</p><h3 className="mt-1 font-serif text-2xl font-semibold">{draft.display_name || t("sampleAgent")}</h3></div><div className="text-right text-[10px] leading-5 text-stone-400">{draft.license_no}<br />{draft.phone}</div></div><h4 className="border-b pb-2 font-serif text-lg font-semibold" style={{ borderColor: draft.accent_color }}>{t("sampleSummary")}</h4><p className="mt-3 rounded-r-lg border-l-4 bg-stone-50 p-4 text-xs leading-5" style={{ borderColor: draft.accent_color }}>{t("sampleBody")}</p><div className="mt-6 grid grid-cols-2 gap-3"><div className="rounded-xl border p-3"><p className="mb-2 text-xs font-bold">{t("sampleHighlights")}</p><span className="block h-1.5 rounded bg-stone-200" /><span className="mt-2 block h-1.5 w-2/3 rounded bg-stone-200" /></div><div className="rounded-xl border p-3"><p className="mb-2 text-xs font-bold">{t("sampleConcerns")}</p><span className="block h-1.5 rounded bg-stone-200" /><span className="mt-2 block h-1.5 w-1/2 rounded bg-stone-200" /></div></div></div></div><p className="mt-3 text-xs leading-5 text-stone-400">{t("previewNote")}</p></aside>
  </div></div>;
}
