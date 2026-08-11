import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShowingsDashboard } from "@/components/showings-dashboard";
import { api, type Showing } from "@/lib/api";
import messages from "@/messages/en.json";

const visitId = "11111111-1111-4111-8111-111111111111";
const buyerId = "33333333-3333-4333-8333-333333333333";

function makeShowing(id: string, propertyName: string, createdAt: string): Showing {
  return {
    id,
    status: "draft",
    processing_status: "ready",
    processing_failed_step: null,
    processing_error: null,
    started_at: createdAt,
    ended_at: createdAt,
    created_at: createdAt,
    updated_at: createdAt,
    property: {
      id: id.replace("1", "2"),
      display_name: propertyName,
      address: `${propertyName} address`,
      attributes: {},
      created_at: createdAt,
      updated_at: createdAt,
    },
    contact: {
      id: buyerId,
      name: "Buyer",
      email: null,
      phone: null,
      notes: null,
      created_at: createdAt,
      updated_at: createdAt,
    },
  };
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}><ShowingsDashboard /></QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

function mockActiveDashboardDependencies() {
  vi.spyOn(api.billing, "get").mockResolvedValue({
    workspace_id: visitId,
    plan: "trial",
    status: "trialing",
    active: true,
    billing_action: "subscribe",
    can_checkout: true,
    can_portal: false,
    stripe_customer_attached: false,
    trial_ends_at: null,
    current_period_end: null,
    cancel_at_period_end: false,
  });
  vi.spyOn(api.contacts, "list").mockResolvedValue([]);
  vi.spyOn(api.properties, "list").mockResolvedValue([]);
}

describe("ShowingsDashboard unassigned properties", () => {
  it("renders an unassigned badge and sends the unassigned filter", async () => {
    vi.spyOn(api.billing, "get").mockResolvedValue({
      workspace_id: visitId,
      plan: "trial",
      status: "trialing",
      active: true,
      billing_action: "subscribe",
      can_checkout: true,
      can_portal: false,
      stripe_customer_attached: false,
      trial_ends_at: null,
      current_period_end: null,
      cancel_at_period_end: false,
    });
    vi.spyOn(api.contacts, "list").mockResolvedValue([]);
    vi.spyOn(api.properties, "list").mockResolvedValue([]);
    const list = vi.spyOn(api.showings, "list").mockResolvedValue({
      items: [{
        id: visitId,
        status: "draft",
        processing_status: "ready",
        processing_failed_step: null,
        processing_error: null,
        started_at: "2026-08-05T10:00:00Z",
        ended_at: "2026-08-05T11:00:00Z",
        created_at: "2026-08-05T10:00:00Z",
        updated_at: "2026-08-05T11:00:00Z",
        property: null,
        contact: null,
      }],
      next_cursor: null,
    });

    renderDashboard();

    expect(await screen.findByText("Unassigned")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "All property assignments" }), { target: { value: "unassigned" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ unassigned: true })));
  });

  it("lists saved properties and sends the selected subject filter", async () => {
    vi.spyOn(api.billing, "get").mockResolvedValue({
      workspace_id: visitId,
      plan: "trial",
      status: "trialing",
      active: true,
      billing_action: "subscribe",
      can_checkout: true,
      can_portal: false,
      stripe_customer_attached: false,
      trial_ends_at: null,
      current_period_end: null,
      cancel_at_period_end: false,
    });
    vi.spyOn(api.contacts, "list").mockResolvedValue([]);
    const propertyId = "22222222-2222-4222-8222-222222222222";
    vi.spyOn(api.properties, "list").mockResolvedValue([{
      id: propertyId,
      display_name: "Maple Street Home",
      address: "123 Maple Street",
      attributes: {},
      created_at: "2026-08-05T10:00:00Z",
      updated_at: "2026-08-05T10:00:00Z",
    }]);
    const list = vi.spyOn(api.showings, "list").mockResolvedValue({ items: [], next_cursor: null });

    renderDashboard();

    const selector = await screen.findByRole("combobox", { name: "All property assignments" });
    expect(await screen.findByRole("option", { name: "Maple Street Home" })).toBeInTheDocument();
    fireEvent.change(selector, { target: { value: propertyId } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ subjectId: propertyId, unassigned: undefined })));
  });
});

describe("ShowingsDashboard billing gate", () => {
  it("removes every new-showing link when the subscription is inactive", async () => {
    vi.spyOn(api.billing, "get").mockResolvedValue({
      workspace_id: visitId,
      plan: "trial",
      status: "trialing",
      active: false,
      billing_action: "subscribe",
      can_checkout: true,
      can_portal: false,
      stripe_customer_attached: false,
      trial_ends_at: "2026-08-01T00:00:00Z",
      current_period_end: null,
      cancel_at_period_end: false,
    });
    vi.spyOn(api.contacts, "list").mockResolvedValue([]);
    vi.spyOn(api.properties, "list").mockResolvedValue([]);
    vi.spyOn(api.showings, "list").mockResolvedValue({ items: [], next_cursor: null });

    renderDashboard();

    expect(await screen.findByText("Your trial has ended")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "New showing" })).not.toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "New showing" })) {
      expect(button).toBeDisabled();
    }
  });
});

describe("ShowingsDashboard cursor pagination", () => {
  it("accumulates pages, preserves backend order, and groups all loaded showings", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("44444444-4444-4444-8444-444444444444", "First home", "2026-08-05T10:00:00Z");
    const second = makeShowing("55555555-5555-4555-8555-555555555555", "Older home", "2026-08-04T10:00:00Z");
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor
        ? { items: [second], next_cursor: null }
        : { items: [first], next_cursor: "cursor-1" },
    );

    renderDashboard();

    expect(await screen.findByText("First home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.loadMore }));
    expect(await screen.findByText("Older home")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buyer" }).nextElementSibling).toHaveTextContent("2");
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "cursor-1", limit: 25 }));
  });

  it("does not render Load more when the backend returns a terminal page", async () => {
    mockActiveDashboardDependencies();
    vi.spyOn(api.showings, "list").mockResolvedValue({
      items: [makeShowing("66666666-6666-4666-8666-666666666666", "Only home", "2026-08-05T10:00:00Z")],
      next_cursor: null,
    });

    renderDashboard();

    expect(await screen.findByText("Only home")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: messages.Home.loadMore })).not.toBeInTheDocument();
  });

  it("shows an in-place disabled loading state and ignores duplicate fetch actions", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("77777777-7777-4777-8777-777777777777", "First home", "2026-08-05T10:00:00Z");
    const second = makeShowing("88888888-8888-4888-8888-888888888888", "Older home", "2026-08-04T10:00:00Z");
    let resolveNext: (page: { items: Showing[]; next_cursor: string | null }) => void = () => undefined;
    const nextPage = new Promise<{ items: Showing[]; next_cursor: string | null }>((resolve) => {
      resolveNext = resolve;
    });
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor ? nextPage : { items: [first], next_cursor: "cursor-1" },
    );

    renderDashboard();

    const loadMore = await screen.findByRole("button", { name: messages.Home.loadMore });
    fireEvent.click(loadMore);
    fireEvent.click(loadMore);

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    const loadingButton = screen.getByRole("button", { name: messages.Home.loadingMore });
    expect(loadingButton).toBeDisabled();
    expect(loadingButton).toHaveAttribute("aria-busy", "true");

    resolveNext({ items: [second], next_cursor: null });
    expect(await screen.findByText("Older home")).toBeInTheDocument();
  });

  it("preserves loaded showings and offers a fetch-next-page retry after a page fails", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("12121212-1212-4212-8212-121212121212", "First home", "2026-08-05T10:00:00Z");
    const second = makeShowing("13131313-1313-4313-8313-131313131313", "Older home", "2026-08-04T10:00:00Z");
    let nextAttempts = 0;
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) => {
      if (!filters.cursor) return { items: [first], next_cursor: "cursor-1" };
      if (nextAttempts++ === 0) throw new Error("page unavailable");
      return { items: [second], next_cursor: null };
    });

    renderDashboard();

    expect(await screen.findByText("First home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.loadMore }));

    expect(await screen.findByText(messages.Home.loadMoreError)).toBeInTheDocument();
    expect(screen.getByText("First home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.retryLoadMore }));

    expect(await screen.findByText("Older home")).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(3);
  });

  it("stops on a repeated cursor, keeps loaded rows, and offers a refresh action", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("17171717-1717-4717-8717-171717171717", "First home", "2026-08-05T10:00:00Z");
    const second = makeShowing("18181818-1818-4818-8818-181818181818", "Older home", "2026-08-04T10:00:00Z");
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor
        ? { items: [second], next_cursor: "cursor-1" }
        : { items: [first], next_cursor: "cursor-1" },
    );

    renderDashboard();

    expect(await screen.findByText("First home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.loadMore }));

    expect(await screen.findByText("Older home")).toBeInTheDocument();
    expect(await screen.findByText(messages.Home.paginationIntegrityError)).toBeInTheDocument();
    expect(screen.getByText("First home")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: messages.Home.refreshShowings })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: messages.Home.loadMore })).not.toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("deduplicates repeated showings across pages in first-seen order", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("14141414-1414-4414-8414-141414141414", "First home", "2026-08-05T10:00:00Z");
    const duplicate = makeShowing(first.id, "Duplicate home", "2026-08-04T10:00:00Z");
    const second = makeShowing("15151515-1515-4515-8515-151515151515", "Older home", "2026-08-03T10:00:00Z");
    vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor
        ? { items: [duplicate, second], next_cursor: null }
        : { items: [first], next_cursor: "cursor-1" },
    );

    renderDashboard();

    expect(await screen.findByText("First home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.loadMore }));
    expect(await screen.findByText("Older home")).toBeInTheDocument();
    expect(screen.queryByText("Duplicate home")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buyer" }).nextElementSibling).toHaveTextContent("2");
  });

  it("starts a fresh pagination chain when a filter changes", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("99999999-9999-4999-8999-999999999999", "All homes", "2026-08-05T10:00:00Z");
    const older = makeShowing("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Older home", "2026-08-04T10:00:00Z");
    const filtered = makeShowing("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Draft home", "2026-08-03T10:00:00Z");
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) => {
      if (filters.status === "draft") return { items: [filtered], next_cursor: null };
      if (filters.cursor === "cursor-1") return { items: [older], next_cursor: null };
      return { items: [first], next_cursor: "cursor-1" };
    });

    renderDashboard();

    expect(await screen.findByText("All homes")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.loadMore }));
    expect(await screen.findByText("Older home")).toBeInTheDocument();

    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "draft" } });

    expect(await screen.findByText("Draft home")).toBeInTheDocument();
    expect(screen.queryByText("Older home")).not.toBeInTheDocument();
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ status: "draft", cursor: undefined, limit: 25 }));
    expect(screen.queryByRole("button", { name: messages.Home.loadMore })).not.toBeInTheDocument();
  });

  it("shows a recoverable property metadata error without hiding the showing list", async () => {
    mockActiveDashboardDependencies();
    const first = makeShowing("16161616-1616-4616-8616-161616161616", "Available home", "2026-08-05T10:00:00Z");
    const properties = vi.spyOn(api.properties, "list")
      .mockRejectedValueOnce(new Error("property metadata unavailable"))
      .mockResolvedValue([]);
    vi.spyOn(api.showings, "list").mockResolvedValue({ items: [first], next_cursor: null });

    renderDashboard();

    expect(await screen.findByText("Available home")).toBeInTheDocument();
    expect(await screen.findByText(messages.Home.propertyFilterError)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: messages.Home.allProperties })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: messages.Home.retryProperties }));

    await waitFor(() => expect(properties).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText(messages.Home.propertyFilterError)).not.toBeInTheDocument());
  });
});
