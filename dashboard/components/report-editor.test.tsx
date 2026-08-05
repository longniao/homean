import { fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import { ReportEditor } from "@/components/report-editor";
import messages from "@/messages/en.json";

const observationId = "11111111-1111-4111-8111-111111111111";
const zoneId = "22222222-2222-4222-8222-222222222222";
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
