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
  const [propertyQuery, setPropertyQuery] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [contactId, setContactId] = useState("");
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState(false);

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
    if (!subjectId && !propertyQuery.trim()) return;
    if (!uploads.some(({ file }) => mediaType(file) === "audio")) {
      toast.error(t("audioRequired"));
      return;
    }
    setPending(true);
    try {
      const showing = await api.showings.create({
        ...(subjectId ? { subject_id: subjectId } : { address: propertyQuery.trim() }),
        contact_id: contactId || null,
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
          <div className="relative mt-5">
            <input
              className="field"
              onChange={(event) => {
                setPropertyQuery(event.target.value);
                if (selected && event.target.value !== selected.address) setSubjectId("");
              }}
              placeholder={t("addressPlaceholder")}
              required
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
          {!subjectId && propertyQuery && (
            <p className="mt-2 text-xs text-stone-500">{t("newPropertyHint")}</p>
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

        <div className="flex justify-end">
          <Button className="h-11 px-5" disabled={pending || uploads.length === 0} type="submit">
            {pending && <LoaderCircle className="animate-spin" />}
            {pending ? t("uploading") : t("createAction")}
          </Button>
        </div>
      </form>
    </div>
  );
}
