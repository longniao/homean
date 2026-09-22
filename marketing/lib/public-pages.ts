// Explicit editorial dates, never the build time. Keep private app paths out.
export const publicPages = [
  { path: "/", updatedAt: "2026-09-22" },
  { path: "/how-it-works/", updatedAt: "2026-09-22" },
  { path: "/about/", updatedAt: "2026-09-22" },
  { path: "/resources/", updatedAt: "2026-09-22" },
  { path: "/resources/showing-report-template/", updatedAt: "2026-09-22" },
  { path: "/resources/sample-showing-report/", updatedAt: "2026-09-22" },
  { path: "/resources/home-comparison-worksheet/", updatedAt: "2026-09-22" },
  { path: "/resources/how-to-compare-homes-after-touring/", updatedAt: "2026-09-22" },
  { path: "/resources/what-to-write-after-a-showing/", updatedAt: "2026-09-22" },
] as const;

export function updatedAt(path: string) {
  const page = publicPages.find(page => page.path === path);
  if (!page) throw new Error(`Public page missing editorial date: ${path}`);
  return page.updatedAt;
}

export function displayDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long", day: "numeric", year: "numeric", timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}
