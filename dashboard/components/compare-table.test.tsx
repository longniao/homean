import { render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import { CompareTable } from "@/components/compare-table";
import type { ShowingDetail } from "@/lib/api";
import messages from "@/messages/en.json";

function showing(id: string, name: string, highlights: number, concerns: number, zoneType = "kitchen"): ShowingDetail {
  const observationId = `${id.slice(0, 8)}-1111-4111-8111-111111111111`;
  const zoneId = `${id.slice(0, 8)}-2222-4222-8222-222222222222`;
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
    property: {
      id: `${id.slice(0, 8)}-3333-4333-8333-333333333333`,
      display_name: name,
      address: `${name} address`,
      attributes: {},
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    },
    contact: null,
    media: [],
    zones: [{ id: zoneId, zone_type: zoneType, position: 0, start_transcript_segment_id: null, end_transcript_segment_id: null }],
    observations: [{
      id: observationId,
      zone_id: zoneId,
      category: "light",
      content: `${name} has good light`,
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
    transcript: [],
    report: {
      id: `${id.slice(0, 8)}-4444-4444-8444-444444444444`,
      template_id: "real_estate_v1",
      status: "confirmed",
      rendered_html: null,
      content: {
        executive_summary: "Summary",
        room_by_room: [],
        highlights: Array.from({ length: highlights }, () => ({ text: "Highlight", observation_ids: [observationId] })),
        concerns: Array.from({ length: concerns }, () => ({ text: "Concern", observation_ids: [observationId] })),
        follow_ups: [],
      },
    },
  };
}

describe("CompareTable", () => {
  it("renders structured counts and zone observations side by side", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <CompareTable
          showings={[
            showing("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Oak House", 2, 1),
            showing("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "Pine House", 1, 3),
          ]}
          zoneLabels={{ kitchen: "Kitchen", other: "Other" }}
        />
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Oak House")).toBeInTheDocument();
    expect(screen.getByText("Pine House")).toBeInTheDocument();
    const highlightRow = screen.getByText("Highlight count").closest("tr");
    expect(highlightRow).not.toBeNull();
    expect(within(highlightRow!).getByText("2")).toBeInTheDocument();
    expect(within(highlightRow!).getByText("1")).toBeInTheDocument();
    expect(screen.getAllByText("Oak House has good light")).toHaveLength(2);
    expect(screen.getAllByText("Pine House has good light")).toHaveLength(2);
  });

  it("renders the configured zone label exactly", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <CompareTable
          showings={[showing("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Oak House", 2, 1)]}
          zoneLabels={{ kitchen: "chef's kitchen", other: "Other" }}
        />
      </NextIntlClientProvider>,
    );

    expect(screen.getByRole("columnheader", { name: "chef's kitchen" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "kitchen" })).not.toBeInTheDocument();
  });

  it("uses the configured other label for unknown or missing zone keys", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <CompareTable
          showings={[showing("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "Oak House", 2, 1, "unconfigured_zone")]}
          zoneLabels={{ other: "Other" }}
        />
      </NextIntlClientProvider>,
    );

    expect(screen.getByRole("columnheader", { name: "Other" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "unconfigured_zone" })).not.toBeInTheDocument();
  });
});
