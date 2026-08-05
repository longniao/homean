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
