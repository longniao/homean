"use client";

import { ArrowRight, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const t = useTranslations("Auth");
  const router = useRouter();
  const search = useSearchParams();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || t("genericError"));
      router.replace(search.get("next") || "/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("genericError"));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-[#f5f5f0] lg:grid-cols-[1.05fr_.95fr]">
      <section className="hidden overflow-hidden bg-[#163d34] p-12 text-white lg:flex lg:flex-col">
        <Link className="font-serif text-3xl font-semibold" href="/">
          Homean
        </Link>
        <div className="my-auto max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[0.18em] text-emerald-200">
            {t("eyebrow")}
          </p>
          <h1 className="font-serif text-6xl leading-[1.03] tracking-[-0.045em]">
            {t("brandTitle")}
          </h1>
          <p className="mt-7 max-w-lg text-lg leading-8 text-emerald-50/75">
            {t("brandBody")}
          </p>
        </div>
        <p className="text-sm text-emerald-100/60">{t("privacy")}</p>
      </section>
      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <Link className="mb-12 block font-serif text-3xl font-semibold lg:hidden" href="/">
            Homean
          </Link>
          <p className="mb-2 text-sm font-semibold text-[#1f6f5b]">
            {mode === "login" ? t("welcomeBack") : t("startTrial")}
          </p>
          <h2 className="font-serif text-4xl font-semibold tracking-[-0.035em]">
            {mode === "login" ? t("loginTitle") : t("signupTitle")}
          </h2>
          <p className="mt-3 text-stone-500">
            {mode === "login" ? t("loginBody") : t("signupBody")}
          </p>
          <form className="mt-9 space-y-5" onSubmit={submit}>
            <label className="block text-sm font-medium">
              {t("email")}
              <input
                autoComplete="email"
                className="field mt-2"
                name="email"
                placeholder={t("emailPlaceholder")}
                required
                type="email"
              />
            </label>
            <label className="block text-sm font-medium">
              {t("password")}
              <input
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className="field mt-2"
                minLength={8}
                name="password"
                placeholder={t("passwordPlaceholder")}
                required
                type="password"
              />
            </label>
            {error && (
              <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
                {error}
              </p>
            )}
            <Button className="h-11 w-full text-sm" disabled={pending} type="submit">
              {pending ? <LoaderCircle className="animate-spin" /> : <ArrowRight />}
              {mode === "login" ? t("loginAction") : t("signupAction")}
            </Button>
          </form>
          <p className="mt-7 text-sm text-stone-500">
            {mode === "login" ? t("noAccount") : t("hasAccount")} {" "}
            <Link
              className="font-semibold text-[#1f6f5b] hover:underline"
              href={mode === "login" ? "/signup" : "/login"}
            >
              {mode === "login" ? t("signupLink") : t("loginLink")}
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
