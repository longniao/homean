import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ClientCompare } from "@/components/client-compare";
import { api, type Showing, type ShowingDetail } from "@/lib/api";
import messages from "@/messages/en.json";

const contactId = "11111111-1111-4111-8111-111111111111";
const showingId = "22222222-2222-4222-8222-222222222222";
const propertyId = "33333333-3333-4333-8333-333333333333";
const zoneId = "44444444-4444-4444-8444-444444444444";
const observationId = "55555555-5555-4555-8555-555555555555";
const reportId = "66666666-6666-4666-8666-666666666666";

function showing(): ShowingDetail {
  return {
    id: showingId,
    status: "confirmed",
    processing_status: "ready",
    processing_failed_step: null,
    processing_error: null,
    started_at: "2026-08-04T10:00:00Z",
    ended_at: "2026-08-04T11:00:00Z",
    created_at: "2026-08-04T10:00:00Z",
    updated_at: "2026-08-04T11:00:00Z",
    property: {
      id: propertyId,
      display_name: "Oak House",
      address: "Oak House address",
      attributes: {},
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T11:00:00Z",
    },
    contact: null,
    media: [],
    zones: [{ id: zoneId, zone_type: "living_room", position: 0, start_transcript_segment_id: null, end_transcript_segment_id: null }],
    observations: [{
      id: observationId,
      zone_id: zoneId,
      category: "light",
      content: "A calm, bright room.",
      source_type: "ai_generated",
      source_transcript_segment_id: null,
      source_media_id: null,
      timestamp_start: null,
      timestamp_end: null,
      ai_model: null,
      prompt_version: null,
      confidence: null,
      flags: {},
      review_status: "confirmed",
      reviewed_by: null,
      reviewed_at: null,
    }],
    transcript: [], markers: [],
    report: {
      id: reportId,
      template_id: "real_estate_v1",
      status: "confirmed",
      rendered_html: null,
      content: {
        executive_summary: "Summary",
        room_by_room: [],
        highlights: [{ text: "Bright", observation_ids: [observationId] }],
        concerns: [],
        follow_ups: [],
      },
    },
  };
}

function showingSummary(id: string): Showing {
  return {
    id,
    status: "confirmed",
    processing_status: "ready",
    processing_failed_step: null,
    processing_error: null,
    started_at: "2026-08-04T10:00:00Z",
    ended_at: "2026-08-04T11:00:00Z",
    created_at: "2026-08-04T10:00:00Z",
    updated_at: "2026-08-04T11:00:00Z",
    property: null,
    contact: null,
  };
}

function renderClientCompare(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}>
        <ClientCompare id={contactId} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("ClientCompare", () => {
  it("loads and passes vertical-config zone labels to the comparison table", async () => {
    vi.spyOn(api.contacts, "get").mockResolvedValue({
      id: contactId,
      name: "Avery Chen",
      email: null,
      phone: null,
      notes: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    });
    vi.spyOn(api.showings, "list").mockResolvedValue({
      items: [{
        id: showingId,
        status: "confirmed",
        processing_status: "ready",
        processing_failed_step: null,
        processing_error: null,
        started_at: "2026-08-04T10:00:00Z",
        ended_at: "2026-08-04T11:00:00Z",
        created_at: "2026-08-04T10:00:00Z",
        updated_at: "2026-08-04T11:00:00Z",
        property: null,
        contact: null,
      }],
      next_cursor: null,
    });
    vi.spyOn(api.showings, "get").mockResolvedValue(showing());
    const vertical = vi.spyOn(api, "vertical").mockResolvedValue({
      zone_taxonomy: ["living_room"],
      observation_schema: ["light"],
      display_labels: {
        zones: { living_room: "great room" },
        observations: { light: "Natural light" },
      },
    });

    renderClientCompare();

    expect(await screen.findByRole("columnheader", { name: "great room" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "living room" })).not.toBeInTheDocument();
    expect(vertical).toHaveBeenCalledTimes(1);
  });

  it("uses the shared error state when vertical config loading fails", async () => {
    vi.spyOn(api.contacts, "get").mockResolvedValue({
      id: contactId,
      name: "Avery Chen",
      email: null,
      phone: null,
      notes: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    });
    vi.spyOn(api.showings, "list").mockResolvedValue({ items: [], next_cursor: null });
    vi.spyOn(api, "vertical").mockRejectedValue(new Error("config unavailable"));

    renderClientCompare();

    expect(await screen.findByText(messages.Common.loadError)).toBeInTheDocument();
  });

  it("loads comparison history across every cursor page", async () => {
    const secondShowingId = "20202020-2020-4020-8020-202020202020";
    const firstDetail = showing();
    const secondDetail = { ...showing(), id: secondShowingId, property: { ...showing().property!, id: "21212121-2121-4121-8121-212121212121", display_name: "Pine House" } };
    vi.spyOn(api.contacts, "get").mockResolvedValue({
      id: contactId,
      name: "Avery Chen",
      email: null,
      phone: null,
      notes: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    });
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor
        ? { items: [showingSummary(secondShowingId)], next_cursor: null }
        : { items: [showingSummary(showingId)], next_cursor: "cursor-1" },
    );
    vi.spyOn(api.showings, "get").mockImplementation(async (id) => id === showingId ? firstDetail : secondDetail);
    vi.spyOn(api, "vertical").mockResolvedValue({
      zone_taxonomy: ["living_room", "other"],
      observation_schema: ["light"],
      display_labels: {
        zones: { living_room: "Living room", other: "Other" },
        observations: { light: "Natural light" },
      },
    });

    renderClientCompare();

    expect(await screen.findByText("Pine House")).toBeInTheDocument();
    expect(screen.getByText("Oak House")).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
    expect(list).toHaveBeenLastCalledWith({ contactId, cursor: "cursor-1", limit: 100 });
  });

  it("uses a distinct all-pages cache key when the first-page cache is fresh", async () => {
    const secondShowingId = "20202020-2020-4020-8020-202020202020";
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    queryClient.setQueryData(["showings", "contact", contactId], {
      items: [showingSummary(showingId)],
      next_cursor: null,
    });
    vi.spyOn(api.contacts, "get").mockResolvedValue({
      id: contactId,
      name: "Avery Chen",
      email: null,
      phone: null,
      notes: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    });
    const list = vi.spyOn(api.showings, "list").mockImplementation(async (filters = {}) =>
      filters.cursor
        ? { items: [showingSummary(secondShowingId)], next_cursor: null }
        : { items: [showingSummary(showingId)], next_cursor: "cursor-1" },
    );
    vi.spyOn(api.showings, "get").mockImplementation(async (id) => ({ ...showing(), id, property: id === showingId ? showing().property : { ...showing().property!, id: "21212121-2121-4121-8121-212121212121", display_name: "Pine House" } }));
    vi.spyOn(api, "vertical").mockResolvedValue({
      zone_taxonomy: ["living_room", "other"],
      observation_schema: ["light"],
      display_labels: {
        zones: { living_room: "Living room", other: "Other" },
        observations: { light: "Natural light" },
      },
    });

    renderClientCompare(queryClient);

    expect(await screen.findByText("Pine House")).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
    expect(list).toHaveBeenLastCalledWith({ contactId, cursor: "cursor-1", limit: 100 });
  });
});
