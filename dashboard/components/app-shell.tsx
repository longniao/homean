"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ContactRound,
  Home,
  LogOut,
  Menu,
  Plus,
  Settings,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("Navigation");
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  const navigation = [
    { href: "/", label: t("home"), icon: Home },
    { href: "/clients", label: t("clients"), icon: ContactRound },
    { href: "/properties", label: t("properties"), icon: Building2 },
    { href: "/settings", label: t("settings"), icon: Settings },
  ];

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  };

  return (
    <div className="min-h-screen text-[#17201d]">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#102c27]/95 text-[#fffdf7] backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-between px-5">
          <Link className="flex items-center gap-3 font-serif text-2xl font-semibold tracking-tight" href="/">
            <span className="grid size-8 place-items-center rounded-full bg-[#e6f36a] font-sans text-xs font-bold text-[#102c27]">H</span>
            <span>Homean</span>
          </Link>
          <Button
            aria-label={open ? t("closeMenu") : t("openMenu")}
            onClick={() => setOpen((value) => !value)}
            size="icon"
            variant="ghost"
          >
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </header>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 -translate-x-full flex-col overflow-hidden border-r border-white/10 bg-[#102c27] p-4 text-[#fffdf7] shadow-2xl shadow-[#102c27]/20 transition-transform lg:translate-x-0",
          open && "translate-x-0",
        )}
      >
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 top-20 size-64 rounded-full border border-[#e6f36a]/10" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-12 top-32 size-36 rounded-full border border-[#e6f36a]/10" />
        <div className="relative mb-9 flex items-center justify-between px-2 pt-2">
          <Link className="flex items-center gap-3" href="/">
            <span className="grid size-10 place-items-center rounded-full bg-[#e6f36a] font-sans text-sm font-bold text-[#102c27]">H</span>
            <span className="font-serif text-3xl font-semibold tracking-[-0.045em]">Homean</span>
          </Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} type="button">
            <X className="size-5" />
          </button>
        </div>
        <Link
          className="relative mb-8 flex h-12 items-center justify-center gap-2 overflow-hidden rounded-full bg-[#e6f36a] px-4 text-sm font-bold text-[#102c27] shadow-[0_10px_30px_rgb(0_0_0_/_0.16)] transition hover:-translate-y-0.5 hover:bg-white"
          href="/showings/new"
          onClick={() => setOpen(false)}
        >
          <Plus className="size-4" />
          {t("newShowing")}
        </Link>
        <nav className="relative space-y-1.5">
          {navigation.map((item, index) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-[#b8c8c1] transition hover:bg-white/8 hover:text-white",
                  active && "bg-[#fffdf7] text-[#102c27] shadow-[0_8px_24px_rgb(0_0_0_/_0.18)]",
                )}
                href={item.href}
                key={item.href}
                onClick={() => setOpen(false)}
              >
                <span className={cn("text-[9px] font-bold tabular-nums text-[#7f9990]", active && "text-[#a73b25]")}>0{index + 1}</span>
                <item.icon className="size-[17px]" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="relative mt-auto rounded-2xl border border-white/10 bg-white/5 p-3">
          <p className="truncate px-2 pt-1 text-sm font-semibold text-white">
            {me?.user.name || me?.user.email || t("account")}
          </p>
          <p className="mb-3 truncate px-2 text-xs text-[#91aaa1]">
            {me?.workspace.name}
          </p>
          <Button className="w-full justify-start text-[#b8c8c1] hover:bg-white/8 hover:text-white" onClick={logout} variant="ghost">
            <LogOut /> {t("logout")}
          </Button>
        </div>
      </aside>
      {open && (
        <button
          aria-label={t("closeMenu")}
          className="fixed inset-0 z-40 bg-[#102c27]/40 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
          type="button"
        />
      )}
      <main className="min-h-screen lg:pl-72">
        <div className="mx-auto w-full max-w-[1500px] px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
          {children}
        </div>
      </main>
    </div>
  );
}
