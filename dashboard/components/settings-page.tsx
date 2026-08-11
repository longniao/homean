"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  ImagePlus,
  LoaderCircle,
  Mail,
  Palette,
  Phone,
  Save,
  UserRound,
} from "lucide-react";
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
  const billing = useQuery({ queryKey: ["billing"], queryFn: api.billing.get });
  const preview = useQuery({
    queryKey: ["branding-preview"],
    queryFn: api.branding.preview,
  });
  const [name, setName] = useState("");
  const [draft, setDraft] = useState<Omit<
    Branding,
    "id" | "logo_key" | "updated_at"
  > | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  useEffect(() => {
    if (me.data) setName(me.data.user.name ?? "");
  }, [me.data]);

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

  const saveProfile = useMutation({
    mutationFn: () => api.updateMe({ name: name.trim() || null }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      toast.success(t("profileSaved"));
    },
    onError: (error) => toast.error(error.message),
  });
  const saveBranding = useMutation({
    mutationFn: () => api.branding.update(draft!),
    onSuccess: async () => {
      toast.success(t("saved"));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["branding"] }),
        queryClient.invalidateQueries({ queryKey: ["branding-preview"] }),
      ]);
    },
    onError: (error) => toast.error(error.message),
  });
  const billingAction = useMutation({
    mutationFn: async () => billing.data?.billing_action === "manage_billing" ? api.billing.portal() : api.billing.checkout(),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (error) => toast.error(error.message),
  });

  const uploadLogo = async (file: File) => {
    setLogoPreview(URL.createObjectURL(file));
    try {
      const presign = await api.branding.presignLogo(file.type);
      const response = await fetch(presign.upload_url, {
        method: "PUT",
        headers: presign.headers,
        body: file,
      });
      if (!response.ok) throw new Error(t("logoFailed"));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["branding"] }),
        queryClient.invalidateQueries({ queryKey: ["branding-preview"] }),
      ]);
      toast.success(t("logoUploaded"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("logoFailed"));
    }
  };

  if (me.isLoading || branding.isLoading || !draft) return <LoadingState />;
  if (!me.data || me.isError || branding.isError) return <ErrorState />;

  const update = (key: keyof typeof draft, value: string) =>
    setDraft((current) =>
      current ? { ...current, [key]: value || null } : current,
    );

  return (
    <div>
      <div className="mb-8">
        <p className="eyebrow mb-3">{t("eyebrow")}</p>
        <h1 className="page-title">{t("title")}</h1>
        <p className="mt-3 text-stone-500">{t("subtitle")}</p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="space-y-6">
          {billing.data && <section className="panel border-emerald-200 bg-emerald-50/40 p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="flex-1"><p className="eyebrow mb-2">{t("billingEyebrow")}</p><h2 className="font-serif text-xl font-semibold">{t("billingTitle")}</h2><p className="mt-1 text-sm text-stone-600">{billing.data.active ? t("billingActive", { plan: billing.data.plan === "trial" ? t("trialPlan") : t("soloPlan") }) : t("billingExpired")}</p></div>
              <Button disabled={billingAction.isPending} onClick={() => billingAction.mutate()}>{billing.data.billing_action === "manage_billing" ? t("manageBilling") : t("subscribe")}</Button>
            </div>
          </section>}
          <form
            className="panel p-5 sm:p-6"
            onSubmit={(event) => {
              event.preventDefault();
              saveProfile.mutate();
            }}
          >
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-xl bg-stone-100 p-2 text-stone-600">
                <UserRound className="size-5" />
              </div>
              <div>
                <h2 className="font-serif text-xl font-semibold">{t("profileTitle")}</h2>
                <p className="text-sm text-stone-500">{t("profileBody")}</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">{t("name")}<input className="field mt-2" onChange={(event) => setName(event.target.value)} value={name} /></label>
              <label className="text-sm font-medium">{t("accountEmail")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.user.email} /></label>
              <label className="text-sm font-medium">{t("workspace")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.workspace.name} /></label>
              <label className="text-sm font-medium">{t("role")}<input className="field mt-2 bg-stone-50" readOnly value={me.data.profile.role.replaceAll("_", " ")} /></label>
            </div>
            <Button className="mt-5" disabled={saveProfile.isPending} type="submit">
              {saveProfile.isPending ? <LoaderCircle className="animate-spin" /> : <Save />} {t("saveProfile")}
            </Button>
          </form>

          <form
            className="panel p-5 sm:p-6"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              saveBranding.mutate();
            }}
          >
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-xl bg-emerald-50 p-2 text-[#1f6f5b]"><Palette className="size-5" /></div>
              <div><h2 className="font-serif text-xl font-semibold">{t("brandingTitle")}</h2><p className="text-sm text-stone-500">{t("brandingBody")}</p></div>
            </div>
            <div className="mb-5 flex items-center gap-4 rounded-xl bg-stone-50 p-4">
              <div className="flex size-16 items-center justify-center overflow-hidden rounded-xl border bg-white">
                {logoPreview ? <Image alt={t("logoPreviewAlt")} className="size-full object-contain" height={64} src={logoPreview} unoptimized width={64} /> : <Building2 className="size-6 text-stone-300" />}
              </div>
              <div>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-semibold shadow-sm"><ImagePlus className="size-4" /> {t("uploadLogo")}<input accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(event) => event.target.files?.[0] && uploadLogo(event.target.files[0])} type="file" /></label>
                <p className="mt-2 text-xs text-stone-400">{t("logoHint")}</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">{t("displayName")}<input className="field mt-2" onChange={(event) => update("display_name", event.target.value)} value={draft.display_name ?? ""} /></label>
              <label className="text-sm font-medium">{t("license")}<input className="field mt-2" onChange={(event) => update("license_no", event.target.value)} value={draft.license_no ?? ""} /></label>
              <label className="text-sm font-medium">{t("email")}<div className="relative mt-2"><Mail className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(event) => update("email", event.target.value)} type="email" value={draft.email ?? ""} /></div></label>
              <label className="text-sm font-medium">{t("phone")}<div className="relative mt-2"><Phone className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" /><input className="field pl-9" onChange={(event) => update("phone", event.target.value)} value={draft.phone ?? ""} /></div></label>
              <label className="text-sm font-medium sm:col-span-2">{t("accent")}<div className="mt-2 flex gap-2"><input aria-label={t("accentPicker")} className="h-11 w-14 rounded-lg border bg-white p-1" onChange={(event) => update("accent_color", event.target.value)} type="color" value={draft.accent_color} /><input className="field" onChange={(event) => update("accent_color", event.target.value)} pattern="^#[0-9A-Fa-f]{6}$" value={draft.accent_color} /></div></label>
            </div>
            <Button className="mt-5" disabled={saveBranding.isPending} type="submit">{saveBranding.isPending ? <LoaderCircle className="animate-spin" /> : <Save />} {t("saveBranding")}</Button>
          </form>
        </div>

        <aside className="xl:sticky xl:top-8 xl:self-start">
          <p className="eyebrow mb-3">{t("previewLabel")}</p>
          <div className="overflow-hidden rounded-2xl border bg-white shadow-xl shadow-stone-900/10">
            {preview.isLoading ? (
              <div className="flex h-96 items-center justify-center text-sm text-stone-500">{t("previewLoading")}</div>
            ) : preview.isError || !preview.data ? (
              <div className="flex h-96 items-center justify-center p-8 text-center text-sm text-red-700">{t("previewError")}</div>
            ) : (
              <iframe className="h-[720px] w-full" sandbox="" srcDoc={preview.data} title={t("previewTitle")} />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
