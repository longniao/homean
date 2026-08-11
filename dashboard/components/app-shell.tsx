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
    <div className="min-h-screen bg-[#f5f5f0] text-stone-900">
      <header className="sticky top-0 z-40 border-b border-stone-200/80 bg-[#f5f5f0]/90 backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-between px-5">
          <Link className="font-serif text-2xl font-semibold tracking-tight" href="/">
            Homean
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
          "fixed inset-y-0 left-0 z-50 flex w-72 -translate-x-full flex-col border-r border-stone-200 bg-[#ecece4] p-5 transition-transform lg:translate-x-0",
          open && "translate-x-0",
        )}
      >
        <div className="mb-10 flex items-center justify-between px-2">
          <Link className="font-serif text-3xl font-semibold tracking-[-0.04em]" href="/">
            Homean
          </Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} type="button">
            <X className="size-5" />
          </button>
        </div>
        <Link
          className="mb-7 flex h-11 items-center justify-center gap-2 rounded-xl bg-[#1f6f5b] px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-[#185b4a]"
          href="/showings/new"
          onClick={() => setOpen(false)}
        >
          <Plus className="size-4" />
          {t("newShowing")}
        </Link>
        <nav className="space-y-1">
          {navigation.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-stone-600 transition hover:bg-white/70 hover:text-stone-950",
                  active && "bg-white text-stone-950 shadow-sm",
                )}
                href={item.href}
                key={item.href}
                onClick={() => setOpen(false)}
              >
                <item.icon className="size-[18px]" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-stone-300/70 pt-5">
          <p className="truncate px-2 text-sm font-medium">
            {me?.user.name || me?.user.email || t("account")}
          </p>
          <p className="mb-3 truncate px-2 text-xs text-stone-500">
            {me?.workspace.name}
          </p>
          <Button className="w-full justify-start" onClick={logout} variant="ghost">
            <LogOut /> {t("logout")}
          </Button>
        </div>
      </aside>
      {open && (
        <button
          aria-label={t("closeMenu")}
          className="fixed inset-0 z-40 bg-stone-900/20 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
          type="button"
        />
      )}
      <main className="min-h-screen lg:pl-72">
        <div className="mx-auto w-full max-w-[1500px] px-5 py-7 sm:px-8 lg:px-10 lg:py-10">
          {children}
        </div>
      </main>
    </div>
  );
}
