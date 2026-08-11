import { fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import { ReportEditor } from "@/components/report-editor";
import messages from "@/messages/en.json";

const observationId = "11111111-1111-4111-8111-111111111111";
const zoneId = "22222222-2222-4222-8222-222222222222";
const otherZoneId = "44444444-4444-4444-8444-444444444444";
const observation = {
  id: observationId,
  zone_id: zoneId,
  category: "light",
  content: "Strong natural light.",
  source_type: "ai_generated",
  source_transcript_segment_id: "33333333-3333-4333-8333-333333333333",
  source_media_id: null,
  timestamp_start: 0,
  timestamp_end: 1000,
  ai_model: "fake",
  prompt_version: "test",
  confidence: 0.9,
  flags: {},
  review_status: "pending",
  reviewed_by: null,
  reviewed_at: null,
};
const otherZoneObservation = {
  ...observation,
  id: "55555555-5555-4555-8555-555555555555",
  zone_id: otherZoneId,
  content: "The other room has strong natural light.",
};
const content = {
  executive_summary: "A bright kitchen.",
  room_by_room: [
    {
      zone_id: zoneId,
      zone_type: "kitchen",
      bullets: [{ text: "Strong natural light.", observation_ids: [observationId] }],
    },
  ],
  highlights: [{ text: "Strong natural light.", observation_ids: [observationId] }],
  concerns: [],
  follow_ups: [],
};

function renderEditor(confirmReasons: string[], onConfirm = vi.fn()) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReportEditor
        confirmDisabled={confirmReasons.length > 0}
        confirmReasons={confirmReasons}
        content={content}
        observations={[observation]}
        onApplyRewrite={vi.fn()}
        onChange={vi.fn()}
        onConfirm={onConfirm}
        onEvidence={vi.fn()}
        onSave={vi.fn()}
        zoneLabels={{ kitchen: "Kitchen" }}
      />
    </NextIntlClientProvider>,
  );
}

describe("ReportEditor confirmation guards", () => {
  it("disables confirmation and surfaces guard reasons", () => {
    renderEditor(["Review one observation first."]);
    expect(screen.getByTestId("confirm-button")).toBeDisabled();
    expect(screen.getByTestId("confirm-guard")).toHaveTextContent(
      "Review one observation first.",
    );
  });

  it("enables confirmation when all guards pass", () => {
    const onConfirm = vi.fn();
    renderEditor([], onConfirm);
    fireEvent.click(screen.getByTestId("confirm-button"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

describe("ReportEditor room evidence", () => {
  it("does not offer another zone's observations when a room has no evidence", () => {
    const roomOnlyContent = {
      ...content,
      room_by_room: [
        {
          zone_id: zoneId,
          zone_type: "kitchen",
          bullets: [],
        },
      ],
      highlights: [],
      concerns: [],
      follow_ups: [],
    };

    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReportEditor
          confirmDisabled
          confirmReasons={[]}
          content={roomOnlyContent}
          observations={[otherZoneObservation]}
          onApplyRewrite={vi.fn()}
          onChange={vi.fn()}
          onConfirm={vi.fn()}
          onEvidence={vi.fn()}
          onSave={vi.fn()}
          zoneLabels={{ kitchen: "Kitchen" }}
        />
      </NextIntlClientProvider>,
    );

    expect(screen.getAllByRole("button", { name: "Add bullet" })[0]).toBeDisabled();
    expect(screen.getByText("No observations are available for this room yet.")).toBeInTheDocument();
    expect(screen.queryByText(otherZoneObservation.content)).not.toBeInTheDocument();
  });

  it("keeps visit-level room sections from offering visit-level evidence", () => {
    const visitLevelContent = {
      ...content,
      room_by_room: [{ zone_id: null, zone_type: null, bullets: [] }],
      highlights: [],
      concerns: [],
      follow_ups: [],
    };

    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReportEditor
          confirmDisabled
          confirmReasons={[]}
          content={visitLevelContent}
          observations={[{ ...observation, zone_id: null }]}
          onApplyRewrite={vi.fn()}
          onChange={vi.fn()}
          onConfirm={vi.fn()}
          onEvidence={vi.fn()}
          onSave={vi.fn()}
          zoneLabels={{}}
        />
      </NextIntlClientProvider>,
    );

    expect(screen.getAllByRole("button", { name: "Add bullet" })[0]).toBeDisabled();
    expect(
      screen.getByText(
        "Visit-level observations belong in highlights, concerns, or follow-up items.",
      ),
    ).toBeInTheDocument();
  });
});
