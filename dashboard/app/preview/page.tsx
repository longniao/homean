/**
 * DEV-ONLY preview page — renders the homepage shell with mock data.
 * Delete this file before shipping to production.
 * Excluded from auth middleware via the matcher pattern (no trailing /).
 */
"use client";

import { Building2, CalendarDays, ContactRound, Home, ListFilter, LogOut, Plus, Search, Settings } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

const MOCK_GROUPS = [
  {
    id: "g1",
    label: "Johnson Family",
    items: [
      { id: "s1", address: "123 Maple Street, Burnaby BC", name: "123 Maple Street", status: "confirmed", date: "Aug 15, 2026" },
      { id: "s2", address: "456 Oak Avenue, Vancouver BC", name: "456 Oak Avenue", status: "draft", date: "Aug 12, 2026" },
      { id: "s3", address: "789 Elm Drive, Richmond BC", name: "789 Elm Drive", status: "sent_to_client", date: "Aug 10, 2026" },
    ],
  },
  {
    id: "g2",
    label: "Chen Family",
    items: [
      { id: "s4", address: "321 Pine Road, North Vancouver BC", name: "321 Pine Road", status: "confirmed", date: "Aug 8, 2026" },
    ],
  },
  {
    id: "g3",
    label: "Unassigned",
    items: [
      { id: "s5", address: "—", name: "Unassigned showing", status: "draft", date: "Aug 7, 2026" },
    ],
  },
];

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-amber-100 text-amber-800",
  confirmed: "bg-emerald-100 text-emerald-800",
  sent_to_client: "bg-sky-100 text-sky-800",
};
const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  sent_to_client: "Sent to client",
};

const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/clients", label: "Clients", icon: ContactRound },
  { href: "/properties", label: "Properties", icon: Building2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function PreviewPage() {
  return (
    <div className="min-h-screen text-[#17201d]">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col overflow-hidden border-r border-white/10 bg-[#102c27] p-4 text-[#fffdf7] shadow-2xl shadow-[#102c27]/20">
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 top-20 size-64 rounded-full border border-[#e6f36a]/10" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-12 top-32 size-36 rounded-full border border-[#e6f36a]/10" />
        <div className="relative mb-9 flex items-center px-2 pt-2">
          <Link className="flex items-center gap-3" href="/">
            <span className="grid size-10 place-items-center rounded-full bg-[#e6f36a] font-sans text-sm font-bold text-[#102c27]">H</span>
            <span className="font-serif text-3xl font-semibold tracking-[-0.045em]">Homean</span>
          </Link>
        </div>
        <Link
          className="relative mb-8 flex h-12 items-center justify-center gap-2 overflow-hidden rounded-full bg-[#e6f36a] px-4 text-sm font-bold text-[#102c27] shadow-[0_10px_30px_rgb(0_0_0_/_0.20)] transition duration-200 hover:-translate-y-1 hover:bg-white hover:shadow-[0_16px_40px_rgb(0_0_0_/_0.25)]"
          href="/showings/new"
        >
          <Plus className="size-4" />
          New Showing
        </Link>
        <nav className="relative space-y-1">
          {NAV.map((item, index) => {
            const active = item.href === "/";
            return (
              <Link
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[#b8c8c1] transition-all duration-150 hover:bg-white/8 hover:text-white",
                  active && "bg-[#e6f36a]/12 text-[#e6f36a] shadow-[inset_0_0_0_1px_rgb(230_243_106_/_18%)]",
                )}
                href={item.href}
                key={item.href}
              >
                <span className={cn("text-[9px] font-bold tabular-nums text-[#7f9990]", active && "text-[#e6f36a]")}>{`0${index + 1}`}</span>
                <item.icon className="size-[17px]" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="relative mt-auto rounded-2xl border border-white/10 bg-white/5 p-3">
          <p className="truncate px-2 pt-1 text-sm font-semibold text-white">Sarah Chen</p>
          <p className="mb-3 truncate px-2 text-xs text-[#91aaa1]">Chen Real Estate Group</p>
          <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#b8c8c1] transition hover:bg-white/8 hover:text-white" type="button">
            <LogOut className="size-4" /> Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="min-h-screen lg:pl-72">
        <div className="mx-auto w-full max-w-[1500px] px-5 py-8 sm:px-8 lg:px-12 lg:py-12">

          {/* Page header */}
          <div className="mb-10 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <p className="eyebrow mb-4">Showing Intelligence</p>
              <h1 className="page-title">Your Showings</h1>
              <p className="mt-5 max-w-2xl text-base leading-7 text-[#59625f]">
                Review AI-generated reports from your property visits, then confirm and deliver to your clients.
              </p>
            </div>
            <Link
              className="inline-flex h-12 shrink-0 items-center gap-2 rounded-full bg-[#102c27] px-6 text-sm font-bold text-[#fffdf7] shadow-[0_8px_24px_rgb(16_44_39_/_0.18)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_12px_32px_rgb(16_44_39_/_0.24)]"
              href="/showings/new"
            >
              <Plus className="size-4" /> New Showing
            </Link>
          </div>

          {/* Filter panel */}
          <div className="panel mb-10 p-4 sm:p-5">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-[#e8ebe3] pb-4">
              <div className="tab-bar">
                {(["client", "property"] as const).map((mode) => (
                  <button
                    aria-selected={mode === "client"}
                    className={cn("tab-btn", mode === "client" && "active")}
                    key={mode}
                    type="button"
                  >
                    {mode === "client" ? <ContactRound className="size-4" /> : <Building2 className="size-4" />}
                    {mode === "client" ? "By Client" : "By Property"}
                  </button>
                ))}
              </div>
              <span className="flex items-center gap-1.5 text-xs font-medium text-[#8fa099]">
                <ListFilter className="size-3.5" /> Filter & search below
              </span>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <label className="relative xl:col-span-2">
                <Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-[#a8b3ae]" />
                <input className="field pl-9" placeholder="Search by address, client, keyword…" />
              </label>
              {["All statuses", "All clients", "All properties"].map((label) => (
                <div className="relative" key={label}>
                  <select className="field appearance-none pr-9">
                    <option>{label}</option>
                  </select>
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#a8b3ae]">▾</span>
                </div>
              ))}
              <div className="grid grid-cols-2 gap-2">
                <input className="field px-2 text-xs" placeholder="From" type="date" />
                <input className="field px-2 text-xs" placeholder="To" type="date" />
              </div>
            </div>
          </div>

          {/* Showing groups */}
          <div className="space-y-10">
            {MOCK_GROUPS.map((group) => (
              <section key={group.id}>
                <div className="mb-4 flex items-center gap-3">
                  <h2 className="font-serif text-xl font-semibold text-[#102c27]">{group.label}</h2>
                  <span className="rounded-full bg-[#e6f36a] px-2.5 py-0.5 text-xs font-bold text-[#102c27] shadow-[0_2px_8px_rgb(230_243_106_/_0.5)]">
                    {group.items.length}
                  </span>
                </div>
                <div className="grid gap-3 xl:grid-cols-2">
                  {group.items.map((showing) => (
                    <div
                      className="panel group flex cursor-pointer items-center gap-4 p-4 transition duration-200 hover:-translate-y-1 hover:border-[#b8c0ba] hover:shadow-[0_20px_50px_rgb(16_44_39_/_0.12)]"
                      key={showing.id}
                    >
                      <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-[#102c27] text-[#e6f36a] shadow-[0_4px_12px_rgb(16_44_39_/_0.25)] transition duration-200 group-hover:scale-110">
                        <Building2 className="size-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <span className="truncate font-semibold transition duration-150 group-hover:text-[#a73b25]">
                            {showing.name}
                          </span>
                          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", STATUS_STYLES[showing.status])}>
                            {STATUS_LABELS[showing.status]}
                          </span>
                        </div>
                        <p className="truncate text-sm text-[#626a67]">{showing.address}</p>
                        <p className="mt-1 text-xs text-[#8fa099]">{group.label} · {showing.date}</p>
                      </div>
                      <span className="text-sm font-bold text-[#a73b25] opacity-0 transition duration-150 group-hover:opacity-100">
                        Open
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>

        </div>
      </main>
    </div>
  );
}
