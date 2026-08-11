import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShowingsDashboard } from "@/components/showings-dashboard";
import { api } from "@/lib/api";
import messages from "@/messages/en.json";

const visitId = "11111111-1111-4111-8111-111111111111";

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}><ShowingsDashboard /></QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

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
    vi.spyOn(api.showings, "list").mockResolvedValue({ items: [], next_cursor: null });

    renderDashboard();

    expect(await screen.findByText("Your trial has ended")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "New showing" })).not.toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "New showing" })) {
      expect(button).toBeDisabled();
    }
  });
});
