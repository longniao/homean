"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, FileAudio, FileImage, FileVideo, LoaderCircle, UploadCloud, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DragEvent, FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/toast-provider";
import { api, uploadWithProgress } from "@/lib/api";
import { cn } from "@/lib/utils";

type UploadItem = { file: File; progress: number; done: boolean };
type PropertySelection = "assigned" | "none";

function mediaType(file: File) {
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type.startsWith("image/")) return "photo";
  return "video";
}

export function NewShowingForm() {
  const t = useTranslations("NewShowing");
  const router = useRouter();
  const toast = useToast();
  const properties = useQuery({ queryKey: ["properties"], queryFn: api.properties.list });
  const contacts = useQuery({ queryKey: ["contacts"], queryFn: api.contacts.list });
  // The attestation wording is server-owned so the visit can record which
  // text was agreed to, not merely that something was.
  const vertical = useQuery({ queryKey: ["vertical-config"], queryFn: api.vertical });
  const [propertyQuery, setPropertyQuery] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [propertySelection, setPropertySelection] = useState<PropertySelection>("assigned");
  const [propertyError, setPropertyError] = useState("");
  const [contactId, setContactId] = useState("");
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState(false);
  const [consentAck, setConsentAck] = useState(false);
  const [consentError, setConsentError] = useState("");

  const matches = useMemo(
    () =>
      (properties.data ?? [])
        .filter((property) =>
          `${property.display_name} ${property.address}`
            .toLowerCase()
            .includes(propertyQuery.toLowerCase()),
        )
        .slice(0, 6),
    [properties.data, propertyQuery],
  );
  const selected = properties.data?.find((property) => property.id === subjectId);

  const addFiles = (files: FileList | File[]) => {
    setUploads((current) => [
      ...current,
      ...Array.from(files).map((file) => ({ file, progress: 0, done: false })),
    ]);
  };
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (propertySelection === "assigned" && !subjectId && !propertyQuery.trim()) {
      setPropertyError(t("propertyRequired"));
      return;
    }
    if (!uploads.some(({ file }) => mediaType(file) === "audio")) {
      toast.error(t("audioRequired"));
      return;
    }
    if (!consentAck) {
      setConsentError(t("consentRequired"));
      return;
    }
    setPending(true);
    try {
      const showing = await api.showings.create({
        ...(propertySelection === "none"
          ? {}
          : subjectId
            ? { subject_id: subjectId }
            : { address: propertyQuery.trim() }),
        contact_id: contactId || null,
        consent_ack: consentAck,
        ...(vertical.data?.consent ? { consent_text_version: vertical.data.consent.version } : {}),
      });
      for (let index = 0; index < uploads.length; index += 1) {
        const item = uploads[index];
        const presign = await api.showings.presign(showing.id, {
          type: mediaType(item.file),
          content_type: item.file.type,
        });
        await uploadWithProgress(presign.upload_url, item.file, presign.headers, (progress) => {
          setUploads((current) =>
            current.map((entry, entryIndex) =>
              entryIndex === index ? { ...entry, progress } : entry,
            ),
          );
        });
        await api.showings.complete(showing.id, presign.media_id);
        setUploads((current) =>
          current.map((entry, entryIndex) =>
            entryIndex === index ? { ...entry, progress: 100, done: true } : entry,
          ),
        );
      }
      await api.showings.finish(showing.id);
      toast.success(t("created"));
      router.push(`/showings/${showing.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("failed"));
      setPending(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <Link className="mb-7 inline-flex items-center gap-2 text-sm font-semibold text-stone-500 hover:text-stone-950" href="/">
        <ArrowLeft className="size-4" /> {t("back")}
      </Link>
      <p className="eyebrow mb-3">{t("eyebrow")}</p>
      <h1 className="page-title">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-stone-500">{t("subtitle")}</p>

      <form className="mt-9 space-y-6" onSubmit={submit}>
        <section className="panel p-5 sm:p-7">
          <div className="mb-5 flex size-9 items-center justify-center rounded-xl bg-emerald-50 text-sm font-bold text-[#1f6f5b]">1</div>
          <h2 className="font-serif text-2xl font-semibold">{t("propertyTitle")}</h2>
          <p className="mt-1 text-sm text-stone-500">{t("propertyBody")}</p>
          <fieldset className="mt-5">
            <legend className="mb-2 text-sm font-semibold text-stone-800">{t("propertyChoiceLabel")}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className={cn("flex cursor-pointer gap-3 rounded-xl border p-3 transition", propertySelection === "assigned" ? "border-emerald-700 bg-emerald-50/60" : "border-stone-200 hover:bg-stone-50")}>
                <input
                  checked={propertySelection === "assigned"}
                  className="mt-1 accent-[#1f6f5b]"
                  name="property-selection"
                  onChange={() => {
                    setPropertySelection("assigned");
                    setPropertyError("");
                  }}
                  type="radio"
                  value="assigned"
                />
                <span>
                  <span className="block text-sm font-semibold">{t("propertyChoiceAssigned")}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-stone-500">{t("propertyChoiceAssignedBody")}</span>
                </span>
              </label>
              <label className={cn("flex cursor-pointer gap-3 rounded-xl border p-3 transition", propertySelection === "none" ? "border-emerald-700 bg-emerald-50/60" : "border-stone-200 hover:bg-stone-50")}>
                <input
                  checked={propertySelection === "none"}
                  className="mt-1 accent-[#1f6f5b]"
                  name="property-selection"
                  onChange={() => {
                    setPropertySelection("none");
                    setPropertyError("");
                  }}
                  type="radio"
                  value="none"
                />
                <span>
                  <span className="block text-sm font-semibold">{t("propertyChoiceNone")}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-stone-500">{t("propertyChoiceNoneBody")}</span>
                </span>
              </label>
            </div>
          </fieldset>
          {propertySelection === "assigned" ? (
            <>
              <div className="relative mt-4">
                <label className="sr-only" htmlFor="property-address">{t("addressLabel")}</label>
                <input
                  aria-describedby={propertyError ? "property-help property-error" : "property-help"}
                  aria-invalid={Boolean(propertyError)}
                  className="field"
                  id="property-address"
                  onChange={(event) => {
                    setPropertyQuery(event.target.value);
                    setPropertyError("");
                    if (selected && event.target.value !== selected.address) setSubjectId("");
                  }}
                  placeholder={t("addressPlaceholder")}
                  value={propertyQuery}
                />
                {propertyQuery && !subjectId && matches.length > 0 && (
                  <div className="absolute inset-x-0 top-12 z-20 overflow-hidden rounded-xl border bg-white shadow-xl">
                    {matches.map((property) => (
                      <button
                        className="block w-full border-b px-4 py-3 text-left last:border-0 hover:bg-stone-50"
                        key={property.id}
                        onClick={() => {
                          setSubjectId(property.id);
                          setPropertyQuery(property.address);
                          setPropertyError("");
                        }}
                        type="button"
                      >
                        <span className="block text-sm font-semibold">{property.display_name}</span>
                        <span className="block text-xs text-stone-500">{property.address}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <p className="mt-2 text-xs text-stone-500" id="property-help">
                {subjectId ? t("savedPropertyHint") : propertyQuery ? t("newPropertyHint") : t("propertyHelp")}
              </p>
              {propertyError && <p className="mt-2 text-sm text-red-700" id="property-error" role="alert">{propertyError}</p>}
            </>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-emerald-200 bg-emerald-50/50 p-4" role="status">
              <p className="text-sm leading-6 text-stone-700">{t("noPropertyHint")}</p>
            </div>
          )}
          <label className="mt-5 block text-sm font-medium">
            {t("clientLabel")}
            <select className="field mt-2" onChange={(event) => setContactId(event.target.value)} value={contactId}>
              <option value="">{t("noClient")}</option>
              {contacts.data?.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}</option>)}
            </select>
          </label>
        </section>

        <section className="panel p-5 sm:p-7">
          <div className="mb-5 flex size-9 items-center justify-center rounded-xl bg-emerald-50 text-sm font-bold text-[#1f6f5b]">2</div>
          <h2 className="font-serif text-2xl font-semibold">{t("uploadTitle")}</h2>
          <p className="mt-1 text-sm text-stone-500">{t("uploadBody")}</p>
          <div
            className={cn(
              "mt-5 flex min-h-52 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-300 bg-stone-50/70 p-6 text-center transition",
              dragging && "border-[#1f6f5b] bg-emerald-50",
            )}
            onDragEnter={() => setDragging(true)}
            onDragLeave={() => setDragging(false)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={drop}
          >
            <UploadCloud className="mb-4 size-8 text-[#1f6f5b]" />
            <p className="font-semibold">{t("dropTitle")}</p>
            <p className="mt-1 text-sm text-stone-500">{t("dropBody")}</p>
            <label className="mt-5 cursor-pointer rounded-lg border bg-white px-3 py-2 text-sm font-semibold shadow-sm hover:bg-stone-50">
              {t("browse")}
              <input
                accept="audio/*,image/*,video/*"
                className="sr-only"
                multiple
                onChange={(event) => event.target.files && addFiles(event.target.files)}
                type="file"
              />
            </label>
          </div>
          {uploads.length > 0 && (
            <div className="mt-4 space-y-2">
              {uploads.map((item, index) => {
                const type = mediaType(item.file);
                const Icon = type === "audio" ? FileAudio : type === "photo" ? FileImage : FileVideo;
                return (
                  <div className="flex items-center gap-3 rounded-xl border bg-white p-3" key={`${item.file.name}-${index}`}>
                    <Icon className="size-5 text-stone-500" />
                    <div className="min-w-0 flex-1">
                      <div className="flex justify-between gap-3 text-sm">
                        <span className="truncate font-medium">{item.file.name}</span>
                        <span className="text-stone-400">{item.done ? t("complete") : `${item.progress}%`}</span>
                      </div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-100">
                        <div className="h-full bg-[#1f6f5b] transition-all" style={{ width: `${item.progress}%` }} />
                      </div>
                    </div>
                    {item.done ? (
                      <CheckCircle2 className="size-5 text-emerald-700" />
                    ) : !pending ? (
                      <button aria-label={t("removeFile")} onClick={() => setUploads((current) => current.filter((_, i) => i !== index))} type="button">
                        <X className="size-4 text-stone-400" />
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <fieldset
          aria-describedby={consentError ? "consent-help consent-error" : "consent-help"}
          className="panel p-5 sm:p-7"
        >
          <legend className="px-1 font-serif text-2xl font-semibold">{t("consentTitle")}</legend>
          <p className="mt-1 text-sm text-stone-500" id="consent-help">{t("consentHelp")}</p>
          <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-stone-200 p-4 transition hover:bg-stone-50">
            <input
              aria-describedby={consentError ? "consent-help consent-error" : "consent-help"}
              aria-invalid={Boolean(consentError)}
              checked={consentAck}
              className="mt-1 size-4 accent-[#1f6f5b]"
              id="consent-attestation"
              onChange={(event) => {
                setConsentAck(event.target.checked);
                setConsentError("");
              }}
              required
              type="checkbox"
            />
            <span className="text-sm font-semibold leading-6 text-stone-800">{vertical.data?.consent?.text ?? t("consentLabel")}</span>
          </label>
          {consentError && <p className="mt-2 text-sm text-red-700" id="consent-error" role="alert">{consentError}</p>}
        </fieldset>

        <div className="flex justify-end">
          <Button className="h-11 px-5" disabled={pending || uploads.length === 0 || !consentAck} type="submit">
            {pending && <LoaderCircle className="animate-spin" />}
            {pending ? t("uploading") : t("createAction")}
          </Button>
        </div>
      </form>
    </div>
  );
}
