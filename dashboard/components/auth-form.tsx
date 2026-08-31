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
      const payload: unknown = await response.json();
      const detail =
        typeof payload === "object" &&
        payload !== null &&
        "detail" in payload &&
        typeof payload.detail === "string"
          ? payload.detail
          : t("genericError");
      if (!response.ok) throw new Error(detail);
      router.replace(search.get("next") || "/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("genericError"));
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[#f4f1e9] lg:grid-cols-[minmax(480px,1.08fr)_minmax(440px,.92fr)]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[#172824] p-8 text-[#fffdf8] lg:flex lg:flex-col xl:p-12">
        <div aria-hidden="true" className="absolute -right-44 -top-40 size-[34rem] rounded-full border border-[#a5b4fc]/15" />
        <div aria-hidden="true" className="absolute -right-20 -top-12 size-[22rem] rounded-full border border-[#a5b4fc]/15" />
        <div aria-hidden="true" className="absolute bottom-[18%] left-[11%] h-px w-[72%] rotate-[-8deg] bg-[#a5b4fc]/20" />
        <Link className="relative flex items-center gap-3" href="/">
          <span aria-hidden="true" className="brand-mark size-10" />
          <span className="text-2xl font-semibold tracking-[-0.03em]">Homean</span>
        </Link>
        <div className="relative my-auto max-w-2xl py-16">
          <p className="mb-8 flex items-center gap-2.5 text-[11px] font-bold uppercase tracking-[0.15em] text-[#a5b4fc] before:size-2 before:rounded-full before:bg-current">
            {t("eyebrow")}
          </p>
          <h1 className="max-w-xl font-serif text-[clamp(4.5rem,7vw,7.5rem)] font-medium leading-[0.82] tracking-[-0.065em]">
            {t("brandTitle")}
          </h1>
          <div className="mt-12 grid max-w-xl grid-cols-[64px_1fr] gap-5 border-t border-white/15 pt-6">
            <span className="font-serif text-3xl text-[#a5b4fc]">01</span>
            <p className="text-base leading-7 text-[#b8c8c1]">{t("brandBody")}</p>
          </div>
        </div>
        <p className="relative max-w-lg border-l-2 border-[#f97316] pl-4 text-xs leading-5 text-[#91aaa1]">
          {t("privacy")}
        </p>
      </section>
      <section className="relative flex items-center justify-center px-5 py-10 sm:px-10 lg:px-14">
        <div aria-hidden="true" className="absolute right-[-8rem] top-[-8rem] size-80 rounded-full bg-[#a5b4fc]/55 blur-3xl" />
        <div className="relative w-full max-w-[31rem] rounded-[1.75rem] border border-[#d2d7cf] bg-[#fffdf8] p-6 shadow-[0_24px_70px_rgb(23_40_36_/_0.12)] sm:p-10 lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
          <Link className="mb-14 flex items-center gap-3 lg:hidden" href="/">
            <span aria-hidden="true" className="brand-mark size-9" />
            <span className="text-2xl font-semibold tracking-[-0.03em]">Homean</span>
          </Link>
          <p className="mb-4 flex items-center gap-2.5 text-[11px] font-bold uppercase tracking-[0.15em] text-[#3730a3] before:size-2 before:rounded-full before:bg-current">
            {mode === "login" ? t("welcomeBack") : t("startTrial")}
          </p>
          <h2 className="max-w-md font-serif text-5xl font-medium leading-[0.9] tracking-[-0.055em] text-[#172824] sm:text-6xl">
            {mode === "login" ? t("loginTitle") : t("signupTitle")}
          </h2>
          <p className="mt-5 max-w-md text-base leading-7 text-[#53635e]">
            {mode === "login" ? t("loginBody") : t("signupBody")}
          </p>
          <form className="mt-10 space-y-5" onSubmit={submit}>
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
              <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
                {error}
              </p>
            )}
            <Button className="h-13 w-full rounded-full bg-[#4f46e5] text-sm font-bold text-white shadow-[0_10px_24px_rgb(79_70_229_/_0.22)] hover:-translate-y-0.5 hover:bg-[#4338ca]" disabled={pending} type="submit">
              {pending ? <LoaderCircle className="animate-spin" /> : <ArrowRight />}
              {mode === "login" ? t("loginAction") : t("signupAction")}
            </Button>
          </form>
          <p className="mt-8 border-t border-[#d8d5cc] pt-6 text-sm text-[#53635e]">
            {mode === "login" ? t("noAccount") : t("hasAccount")} {" "}
            <Link
              className="font-bold text-[#3730a3] underline-offset-4 hover:underline"
              href={mode === "login" ? "/signup" : "/login"}
            >
              {mode === "login" ? t("signupLink") : t("loginLink")}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
