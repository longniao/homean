"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarDays, ContactRound, ListFilter, LoaderCircle, Plus, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { useOptionalToast } from "@/components/toast-provider";
import { Button } from "@/components/ui/button";
import { api, dedupeShowingsById, type Showing } from "@/lib/api";
import { cn } from "@/lib/utils";
import { tourDate } from "@/lib/tour-date";

type ViewMode = "client" | "property";
const SHOWINGS_PAGE_SIZE = 25;

export function ShowingsDashboard() {
  const t = useTranslations("Home");
  const common = useTranslations("Common");
  const queryClient = useQueryClient();
  const [view, setView] = useState<ViewMode>("client");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [contactId, setContactId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [query, setQuery] = useState("");
  const toast = useOptionalToast();
  const billing = useQuery({ queryKey: ["billing"], queryFn: api.billing.get });
  const billingAction = useMutation({
    mutationFn: async () => billing.data?.billing_action === "manage_billing" ? api.billing.portal() : api.billing.checkout(),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (error) => toast?.error(error.message),
  });
  const contacts = useQuery({ queryKey: ["contacts"], queryFn: api.contacts.list });
  const properties = useQuery({ queryKey: ["properties"], queryFn: api.properties.list });
  const showings = useInfiniteQuery({
    queryKey: ["showings", status, dateFrom, dateTo, contactId, subjectId, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api.showings.list({
        status: status || undefined,
        dateFrom: dateFrom ? new Date(`${dateFrom}T00:00:00`).toISOString() : undefined,
        dateTo: dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined,
        contactId: contactId || undefined,
        subjectId: subjectId && subjectId !== "unassigned" ? subjectId : undefined,
        unassigned: subjectId === "unassigned" ? true : undefined,
        query: query || undefined,
        cursor: pageParam ?? undefined,
        limit: SHOWINGS_PAGE_SIZE,
      }),
    getNextPageParam: (lastPage, _allPages, _lastPageParam, allPageParams) => {
      const nextCursor = lastPage.next_cursor ?? undefined;
      return nextCursor !== undefined && allPageParams.includes(nextCursor)
        ? undefined
        : nextCursor;
    },
  });
  const fetchingNextPage = useRef(false);
  useEffect(() => {
    fetchingNextPage.current = false;
  }, [status, dateFrom, dateTo, contactId, subjectId, query]);

  const loadMore = () => {
    if (!showings.hasNextPage || showings.isFetchingNextPage || fetchingNextPage.current) return;
    fetchingNextPage.current = true;
    void showings.fetchNextPage().finally(() => {
      fetchingNextPage.current = false;
    });
  };

  const loadedShowings = useMemo(
    () => dedupeShowingsById(showings.data?.pages.flatMap((page) => page.items) ?? []),
    [showings.data?.pages],
  );
  const hasLoadedPages = (showings.data?.pages.length ?? 0) > 0;
  const paginationIntegrityError = useMemo(() => {
    const pages = showings.data?.pages ?? [];
    const pageParams = showings.data?.pageParams ?? [];
    const nextCursor = pages.at(-1)?.next_cursor;
    return nextCursor !== null && nextCursor !== undefined && pageParams.includes(nextCursor);
  }, [showings.data?.pageParams, showings.data?.pages]);
  const showingsQueryKey = ["showings", status, dateFrom, dateTo, contactId, subjectId, query] as const;

  const refreshShowings = () => {
    void queryClient.resetQueries({ queryKey: showingsQueryKey, exact: true });
  };

  const groups = useMemo(() => {
    const result = new Map<string, { label: string; items: Showing[] }>();
    for (const showing of loadedShowings) {
      const id =
        view === "client" ? showing.contact?.id ?? "unassigned-client" : showing.property?.id ?? "unassigned-property";
      const label =
        view === "client"
          ? showing.contact?.name ?? t("unassignedClient")
          : showing.property?.display_name ?? t("unassignedProperty");
      const current = result.get(id) ?? { label, items: [] };
      current.items.push(showing);
      result.set(id, current);
    }
    return [...result.entries()];
  }, [loadedShowings, t, view]);

  return (
    <div>
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow mb-3">{t("eyebrow")}</p>
          <h1 className="page-title">{t("title")}</h1>
          <p className="mt-3 max-w-2xl text-stone-500">{t("subtitle")}</p>
        </div>
        {billing.data?.active === false ? (
          <Button className="h-10 px-4" disabled><Plus /> {t("newShowing")}</Button>
        ) : (
          <Button className="h-10 px-4" nativeButton={false} render={<Link href="/showings/new" />}><Plus /> {t("newShowing")}</Button>
        )}
      </div>

      {billing.data && !billing.data.active && (
        <div className="mb-6 flex flex-col gap-4 rounded-2xl border border-amber-300 bg-amber-50 p-5 sm:flex-row sm:items-center">
          <div className="flex-1">
            <p className="font-semibold text-amber-950">{t("upgradeTitle")}</p>
            <p className="mt-1 text-sm leading-6 text-amber-900/80">{t("upgradeBody")}</p>
          </div>
          <Button disabled={billingAction.isPending} onClick={() => billingAction.mutate()}>{billing.data.billing_action === "manage_billing" ? common("manageBilling") : t("upgradeAction")}</Button>
        </div>
      )}

      <div className="panel mb-6 p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-xl bg-stone-100 p-1">
            {(["client", "property"] as const).map((mode) => (
              <button
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-500 transition",
                  view === mode && "bg-white text-stone-950 shadow-sm",
                )}
                key={mode}
                onClick={() => setView(mode)}
                type="button"
              >
                {mode === "client" ? <ContactRound className="size-4" /> : <Building2 className="size-4" />}
                {mode === "client" ? t("byClient") : t("byProperty")}
              </button>
            ))}
          </div>
          <span className="flex items-center gap-2 text-xs font-medium text-stone-400">
            <ListFilter className="size-4" /> {t("filterHint")}
          </span>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label className="relative xl:col-span-2">
            <span className="sr-only">{t("search")}</span>
            <Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-stone-400" />
            <input
              className="field pl-9"
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("searchPlaceholder")}
              value={query}
            />
          </label>
          <select className="field" onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="">{t("allStatuses")}</option>
            <option value="draft">{t("draft")}</option>
            <option value="confirmed">{t("confirmed")}</option>
            <option value="sent_to_client">{t("sent")}</option>
          </select>
          <select className="field" onChange={(event) => setContactId(event.target.value)} value={contactId}>
            <option value="">{t("allClients")}</option>
            {contacts.data?.map((contact) => (
              <option key={contact.id} value={contact.id}>{contact.name}</option>
            ))}
          </select>
          <select aria-describedby={properties.isError ? "property-filter-status" : undefined} aria-label={t("allProperties")} className="field" disabled={properties.isError} onChange={(event) => setSubjectId(event.target.value)} value={subjectId}>
            <option value="">{t("allProperties")}</option>
            <option value="unassigned">{t("unassignedProperty")}</option>
            {properties.data?.map((property) => (
              <option key={property.id} value={property.id}>{property.display_name}</option>
            ))}
          </select>
          <div className="grid grid-cols-2 gap-2 xl:col-span-1">
            <input aria-label={t("dateFrom")} className="field px-2 text-xs" onChange={(e) => setDateFrom(e.target.value)} type="date" value={dateFrom} />
            <input aria-label={t("dateTo")} className="field px-2 text-xs" onChange={(e) => setDateTo(e.target.value)} type="date" value={dateTo} />
          </div>
        </div>
        {properties.isError && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-950" id="property-filter-status" role="alert">
            <p>{t("propertyFilterError")}</p>
            <Button onClick={() => void properties.refetch()} size="sm" variant="outline">{t("retryProperties")}</Button>
          </div>
        )}
      </div>

      {showings.isLoading && !hasLoadedPages ? (
        <LoadingState />
      ) : showings.isError && !hasLoadedPages ? (
        <ErrorState retry={() => showings.refetch()} />
      ) : (
        <>
          {(showings.isFetchNextPageError || paginationIntegrityError) && (
            <div aria-live="polite" className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950" role="alert">
              <p>{paginationIntegrityError ? t("paginationIntegrityError") : t("loadMoreError")}</p>
              <Button disabled={showings.isFetchingNextPage} onClick={paginationIntegrityError ? refreshShowings : () => void showings.fetchNextPage()} size="sm" variant="outline">{paginationIntegrityError ? t("refreshShowings") : t("retryLoadMore")}</Button>
            </div>
          )}
          {groups.length === 0 ? (
            <div className="panel flex min-h-80 flex-col items-center justify-center p-8 text-center">
              <div className="mb-5 rounded-2xl bg-emerald-50 p-4 text-[#1f6f5b]">
                <CalendarDays className="size-7" />
              </div>
              <h2 className="font-serif text-2xl font-semibold">{t("emptyTitle")}</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-stone-500">{t("emptyBody")}</p>
              {billing.data?.active === false ? (
                <Button className="mt-6" disabled><Plus /> {t("newShowing")}</Button>
              ) : (
                <Button className="mt-6" nativeButton={false} render={<Link href="/showings/new" />}><Plus /> {t("newShowing")}</Button>
              )}
            </div>
          ) : (
            <div className="space-y-8">
              {groups.map(([id, group]) => (
                <section key={id}>
                  <div className="mb-3 flex items-center gap-3">
                    <h2 className="font-serif text-xl font-semibold">{group.label}</h2>
                    <span className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-semibold text-stone-600">
                      {group.items.length}
                    </span>
                  </div>
                  <div className="grid gap-3 xl:grid-cols-2">
                    {group.items.map((showing) => (
                      <Link
                        className="panel group flex items-center gap-4 p-4 transition hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-md"
                        href={`/showings/${showing.id}`}
                        key={showing.id}
                      >
                        <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-[#ecece4] text-stone-600">
                          <Building2 className="size-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="mb-1 flex flex-wrap items-center gap-2">
                            <h3 className="truncate font-semibold group-hover:text-[#1f6f5b]">
                              {showing.property?.display_name ?? t("unassignedProperty")}
                            </h3>
                            {!showing.property && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">{t("unassignedBadge")}</span>}
                            <StatusBadge showing={showing} />
                          </div>
                          <p className="truncate text-sm text-stone-500">{showing.property?.address ?? t("unassignedProperty")}</p>
                          <p className="mt-1 text-xs text-stone-400">
                            {showing.contact?.name ?? t("unassignedClient")} · {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(tourDate(showing))}
                          </p>
                        </div>
                        <span className="text-sm font-semibold text-[#1f6f5b] opacity-0 transition group-hover:opacity-100">
                          {common("open")}
                        </span>
                      </Link>
                    ))}
                  </div>
                </section>
              ))}
              {showings.hasNextPage && !showings.isFetchNextPageError && !paginationIntegrityError && (
                <div aria-live="polite" className="flex justify-center pt-2">
                  <Button
                    aria-busy={showings.isFetchingNextPage}
                    className="min-w-40"
                    disabled={showings.isFetchingNextPage}
                    onClick={loadMore}
                    type="button"
                    variant="outline"
                  >
                    {showings.isFetchingNextPage && <LoaderCircle aria-hidden="true" className="animate-spin" />}
                    {showings.isFetchingNextPage ? t("loadingMore") : t("loadMore")}
                  </Button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
