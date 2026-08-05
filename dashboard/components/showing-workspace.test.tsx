import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DeliveryPanel,
  ShowingWorkspace,
} from "@/components/showing-workspace";
import { ToastProvider } from "@/components/toast-provider";
import { api, type ShowingDetail } from "@/lib/api";
import messages from "@/messages/en.json";

const visitId = "11111111-1111-4111-8111-111111111111";
const propertyId = "22222222-2222-4222-8222-222222222222";
const zoneId = "33333333-3333-4333-8333-333333333333";
const observationId = "44444444-4444-4444-8444-444444444444";

const showing: ShowingDetail = {
  id: visitId,
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
    display_name: "42 Pipeline Avenue",
    address: "42 Pipeline Avenue",
    attributes: {},
    created_at: "2026-08-04T10:00:00Z",
    updated_at: "2026-08-04T10:00:00Z",
  },
  contact: null,
  media: [],
  zones: [
    {
      id: zoneId,
      zone_type: "kitchen",
      position: 0,
      start_transcript_segment_id: null,
      end_transcript_segment_id: null,
    },
  ],
  observations: [
    {
      id: observationId,
      zone_id: zoneId,
      category: "light",
      content: "Strong natural light.",
      source_type: "ai_generated",
      source_transcript_segment_id: null,
      source_media_id: null,
      timestamp_start: null,
      timestamp_end: null,
      ai_model: "fake",
      prompt_version: "test",
      confidence: 0.9,
      flags: {},
      review_status: "confirmed",
      reviewed_by: propertyId,
      reviewed_at: "2026-08-04T11:00:00Z",
    },
  ],
  transcript: [],
  report: null,
};

function renderWithProviders(children: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Showing workspace API-backed metadata", () => {
  it("renders persisted delivery open counts and send history", async () => {
    vi.spyOn(api.showings, "delivery").mockResolvedValue({
      share_links: [
        {
          token: "private-token",
          url: "https://reports.example/r/private-token",
          created_at: "2026-08-04T12:00:00Z",
          expires_at: null,
          revoked: false,
          open_count: 3,
        },
      ],
      sends: [
        {
          channel: "email",
          to_email: "buyer@example.com",
          sent_at: "2026-08-04T12:01:00Z",
        },
      ],
    });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect(await screen.findByText("Recorded opens: 3")).toBeInTheDocument();
    expect(screen.getByText("Private link · 3 opens")).toBeInTheDocument();
    expect(screen.getByText("Email sent to buyer@example.com")).toBeInTheDocument();
  });

  it("renders category labels returned by the vertical config API", async () => {
    vi.spyOn(api.showings, "get").mockResolvedValue({ ...showing, status: "draft" });
    vi.spyOn(api, "vertical").mockResolvedValue({
      zone_taxonomy: ["kitchen"],
      observation_schema: ["light", "follow_up"],
      display_labels: {
        zones: { kitchen: "Kitchen" },
        observations: { light: "Natural light", follow_up: "Follow-up" },
      },
    });

    renderWithProviders(<ShowingWorkspace id={visitId} />);
    fireEvent.click(await screen.findByRole("button", { name: /Observations/ }));

    expect(await screen.findByRole("option", { name: "Natural light" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Follow-up" })).toBeInTheDocument();
  });

  it("blocks confirmation and attaches a property to an unassigned showing", async () => {
    const assignedProperty = showing.property!;
    const subjectless: ShowingDetail = {
      ...showing,
      status: "draft",
      property: null,
      report: {
        id: "55555555-5555-4555-8555-555555555555",
        template_id: "real_estate_v1",
        status: "pending_review",
        rendered_html: null,
        content: {
          executive_summary: "A bright kitchen.",
          room_by_room: [],
          highlights: [{ text: "Strong natural light.", observation_ids: [observationId] }],
          concerns: [],
          follow_ups: [],
        },
      },
    };
    vi.spyOn(api.showings, "get").mockResolvedValue(subjectless);
    vi.spyOn(api, "vertical").mockResolvedValue({
      zone_taxonomy: ["kitchen"],
      observation_schema: ["light"],
      display_labels: { zones: { kitchen: "Kitchen" }, observations: { light: "Natural light" } },
    });
    vi.spyOn(api.properties, "list").mockResolvedValue([assignedProperty]);
    const attach = vi.spyOn(api.showings, "attachProperty").mockResolvedValue({
      ...subjectless,
      property: assignedProperty,
    });

    renderWithProviders(<ShowingWorkspace id={visitId} />);

    expect(await screen.findByText("Attach a property before confirming the report.")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-button")).toBeDisabled();
    expect(screen.getByTestId("attach-property-panel")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Saved property" }), { target: { value: propertyId } });
    const attachButton = screen.getByRole("button", { name: "Attach property" });
    await waitFor(() => expect(attachButton).toBeEnabled());
    fireEvent.click(attachButton);

    await waitFor(() => expect(attach).toHaveBeenCalledWith(visitId, { subject_id: propertyId }));
    expect(await screen.findByText("Property attached to this showing.")).toBeInTheDocument();
  });
});
