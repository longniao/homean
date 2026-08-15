import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShowingWorkspace } from "@/components/showing-workspace";
import { ToastProvider } from "@/components/toast-provider";
import { api, type ShowingDetail } from "@/lib/api";
import messages from "@/messages/en.json";

const visitId = "11111111-1111-4111-8111-111111111111";
const propertyId = "22222222-2222-4222-8222-222222222222";
const mediaId = "33333333-3333-4333-8333-333333333333";
const segmentId = "44444444-4444-4444-8444-444444444444";
const markerId = "55555555-5555-4555-8555-555555555555";

const vertical = {
  zone_taxonomy: ["kitchen"],
  observation_schema: ["pro"],
  display_labels: {
    zones: { kitchen: "Kitchen" },
    observations: { pro: "Pro" },
  },
};

function showing(transcriptSegmentId: string | null): ShowingDetail {
  return {
    id: visitId,
    status: "draft",
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
    media: [
      {
        id: mediaId,
        type: "audio",
        content_type: "audio/mp4",
        timestamp_offset_ms: null,
        status: "uploaded",
        size_bytes: 1,
        created_at: "2026-08-04T10:00:00Z",
      },
    ],
    zones: [],
    observations: [],
    transcript: [
      {
        id: segmentId,
        raw_media_id: mediaId,
        text: "The kitchen has excellent natural light.",
        original_text: null,
        timestamp_start: 1_000,
        timestamp_end: 2_500,
        confidence: 0.99,
      },
    ],
    markers: [
      {
        id: markerId,
        marker_type: "voice_tag",
        timestamp_offset_ms: 1_200,
        transcript_segment_id: transcriptSegmentId,
        created_at: "2026-08-04T10:00:00Z",
      },
    ],
    report: null,
  };
}

function renderWorkspace(detail: ShowingDetail) {
  vi.spyOn(api.showings, "get").mockResolvedValue(detail);
  vi.spyOn(api, "vertical").mockResolvedValue(vertical);
  vi.spyOn(api.showings, "mediaDownload").mockResolvedValue({
    download_url: "https://media.example/showing.mp4",
    expires_in: 300,
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <ShowingWorkspace id={visitId} />
        </ToastProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

afterEach(() => {
  vi.restoreAllMocks();
  if (originalScrollIntoView) {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: originalScrollIntoView,
    });
  } else {
    Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
  }
});

describe("voice tag jump points", () => {
  it("clicks a resolved tag to scroll to its transcript and seek the audio", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);

    renderWorkspace(showing(segmentId));
    fireEvent.click(await screen.findByRole("button", { name: /^Transcript/ }));

    const tag = await screen.findByRole("button", { name: "Tag 1 · 00:01" });
    await waitFor(() => expect(document.querySelector("audio")).toBeInTheDocument());
    fireEvent.click(tag);

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    expect(document.querySelector("audio")).toHaveProperty("currentTime", 1.2);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("does not render a jump control for an unresolved tag", async () => {
    renderWorkspace(showing(null));
    fireEvent.click(await screen.findByRole("button", { name: /^Transcript/ }));

    expect(await screen.findByText("The kitchen has excellent natural light.")).toBeInTheDocument();
    expect(screen.queryByText(messages.Transcript.voiceTags)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Tag/ })).not.toBeInTheDocument();
  });
});
