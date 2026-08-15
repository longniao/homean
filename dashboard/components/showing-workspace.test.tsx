import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DeliveryPanel,
  ShowingWorkspace,
} from "@/components/showing-workspace";
import { ToastProvider } from "@/components/toast-provider";
import { api, getPublicReportPdfUrl, type ShowingDetail } from "@/lib/api";
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
  transcript: [], markers: [],
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

const originalClipboard = navigator.clipboard;
const originalExecCommand = document.execCommand;

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: originalClipboard,
  });
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: originalExecCommand,
  });
});

describe("Showing workspace API-backed metadata", () => {
  it("derives only the canonical public PDF route", () => {
    expect(getPublicReportPdfUrl("https://reports.example/r/token?source=dashboard#pdf")).toBe(
      "https://reports.example/r/token/pdf",
    );
    expect(getPublicReportPdfUrl("https://reports.example/not-a-report")).toBeNull();
    expect(getPublicReportPdfUrl("javascript:/r/token")).toBeNull();
  });

  it("renders persisted delivery open counts and send history", async () => {
    vi.spyOn(api.showings, "delivery").mockResolvedValue({
      share_links: [
        {
          id: "55555555-5555-4555-8555-555555555555",
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
          send_id: "88888888-8888-4888-8888-888888888888",
          channel: "email",
          to_email: "buyer@example.com",
          status: "sent",
          attempt_count: 1,
          last_attempt_at: "2026-08-04T12:01:00Z",
          sent_at: "2026-08-04T12:01:00Z",
          error: null,
        },
      ],
    });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect(await screen.findByText("Recorded opens: 3")).toBeInTheDocument();
    expect(screen.getByText("Private link · 3 opens")).toBeInTheDocument();
    expect(screen.getByText("Email sent to buyer@example.com")).toBeInTheDocument();
    const pdfLink = screen.getByRole("link", { name: messages.Delivery.openPdf });
    expect(pdfLink).toHaveAttribute("href", "https://reports.example/r/private-token/pdf");
    expect(pdfLink).toHaveAttribute("target", "_blank");
  });

  it("hides the PDF action for revoked and expired share links", async () => {
    vi.spyOn(api.showings, "delivery").mockResolvedValue({
      share_links: [
        {
          id: "55555555-5555-4555-8555-555555555555",
          token: "revoked-token",
          url: "https://reports.example/r/revoked-token",
          created_at: "2026-08-04T12:00:00Z",
          expires_at: null,
          revoked: true,
          open_count: 0,
        },
        {
          id: "66666666-6666-4666-8666-666666666666",
          token: "expired-token",
          url: "https://reports.example/r/expired-token",
          created_at: "2026-08-04T12:00:00Z",
          expires_at: "2026-08-04T12:30:00Z",
          revoked: false,
          open_count: 0,
        },
      ],
      sends: [],
    });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect(await screen.findAllByText("Private link · 0 opens")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: messages.Delivery.openPdf })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: messages.Delivery.copyLinkAction })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: messages.Delivery.revokeLink })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: messages.Delivery.openLink })).not.toBeInTheDocument();
  });

  it("blocks email retry and explains an unknown delivery outcome", async () => {
    vi.spyOn(api.showings, "delivery").mockResolvedValue({
      share_links: [],
      sends: [
        {
          send_id: "88888888-8888-4888-8888-888888888888",
          channel: "email",
          to_email: "buyer@example.com",
          status: "outcome_unknown",
          attempt_count: 1,
          last_attempt_at: "2026-08-04T12:01:00Z",
          sent_at: "2026-08-04T12:01:00Z",
          error: "The delivery outcome is unknown.",
        },
      ],
    });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect(await screen.findAllByText(messages.Delivery.emailOutcomeUnknown)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Send report" })).toBeDisabled();
  });

  it("creates a link without auto-copying and copies it only after an explicit action", async () => {
    const shareUrl = "https://reports.example/r/sent-token";
    const send = vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: shareUrl,
      to_email: null,
    });
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [], sends: [] });
    const writeText = vi.fn().mockResolvedValue(undefined);
    const invalidateQueries = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));

    await waitFor(() => expect(send).toHaveBeenCalledWith(visitId, { channel: "link_only" }));
    await waitFor(() => expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["showings"] }));
    expect(writeText).not.toHaveBeenCalled();
    expect(await screen.findByDisplayValue(shareUrl)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(shareUrl));
    expect(await screen.findByText("Private report link copied.")).toBeInTheDocument();
  });

  it("keeps the returned URL visible while an existing active link refresh is delayed", async () => {
    const existingUrl = "https://reports.example/r/existing-token";
    const returnedUrl = "https://reports.example/r/new-token";
    const existingLink = {
      id: "55555555-5555-4555-8555-555555555555",
      token: "existing-token",
      url: existingUrl,
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: false,
      open_count: 0,
    };
    let resolveRefresh!: (value: { share_links: typeof existingLink[]; sends: never[] }) => void;
    const delayedRefresh = new Promise<{ share_links: typeof existingLink[]; sends: never[] }>((resolve) => {
      resolveRefresh = resolve;
    });
    vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: returnedUrl,
      to_email: null,
    });
    const delivery = vi.spyOn(api.showings, "delivery")
      .mockResolvedValueOnce({ share_links: [existingLink], sends: [] })
      .mockReturnValueOnce(delayedRefresh);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));
    await waitFor(() => expect(delivery).toHaveBeenCalledTimes(2));
    expect(screen.getAllByDisplayValue(existingUrl).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByDisplayValue(returnedUrl)).toBeInTheDocument();
    expect(writeText).not.toHaveBeenCalled();

    const returnedInput = screen.getByDisplayValue(returnedUrl);
    fireEvent.click(within(returnedInput.parentElement as HTMLElement).getByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(returnedUrl));

    resolveRefresh({ share_links: [existingLink], sends: [] });
  });

  it("keeps the returned URL visible when refresh data is stale and contains another active link", async () => {
    const staleUrl = "https://reports.example/r/stale-token";
    const returnedUrl = "https://reports.example/r/fresh-token";
    const staleLink = {
      id: "55555555-5555-4555-8555-555555555555",
      token: "stale-token",
      url: staleUrl,
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: false,
      open_count: 0,
    };
    vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: returnedUrl,
      to_email: null,
    });
    const delivery = vi.spyOn(api.showings, "delivery")
      .mockResolvedValueOnce({ share_links: [], sends: [] })
      .mockResolvedValueOnce({ share_links: [staleLink], sends: [] });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));
    await waitFor(() => expect(delivery).toHaveBeenCalledTimes(2));
    expect(screen.getAllByDisplayValue(staleUrl).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByDisplayValue(returnedUrl)).toBeInTheDocument();

    const returnedInput = screen.getByDisplayValue(returnedUrl);
    fireEvent.click(within(returnedInput.parentElement as HTMLElement).getByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(returnedUrl));
  });

  it("keeps the returned URL visible when delivery refresh fails", async () => {
    const existingUrl = "https://reports.example/r/existing-before-failure";
    const returnedUrl = "https://reports.example/r/recoverable-after-failure";
    const existingLink = {
      id: "55555555-5555-4555-8555-555555555555",
      token: "existing-before-failure",
      url: existingUrl,
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: false,
      open_count: 0,
    };
    vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: returnedUrl,
      to_email: null,
    });
    const delivery = vi.spyOn(api.showings, "delivery")
      .mockResolvedValueOnce({ share_links: [existingLink], sends: [] })
      .mockRejectedValueOnce(new Error("delivery refresh failed"));
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));
    await waitFor(() => expect(delivery).toHaveBeenCalledTimes(2));
    const returnedInput = await screen.findByDisplayValue(returnedUrl);
    expect(screen.getByDisplayValue(existingUrl)).toBeInTheDocument();

    fireEvent.click(within(returnedInput.parentElement as HTMLElement).getByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(returnedUrl));
  });

  it("uses the browser copy fallback when Clipboard API rejects", async () => {
    const shareUrl = "https://reports.example/r/fallback-token";
    vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: shareUrl,
      to_email: null,
    });
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [], sends: [] });
    const writeText = vi.fn().mockRejectedValue(new Error("Clipboard unavailable"));
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    Object.defineProperty(document, "execCommand", { configurable: true, value: execCommand });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));

    await waitFor(() => expect(screen.getByDisplayValue(shareUrl)).toBeInTheDocument());
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(shareUrl));
    await waitFor(() => expect(execCommand).toHaveBeenCalledWith("copy"));
    expect(await screen.findByText(messages.Delivery.linkCopied)).toBeInTheDocument();
  });

  it("reports a clear error when both copy methods fail", async () => {
    const shareUrl = "https://reports.example/r/uncopyable-token";
    vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: shareUrl,
      to_email: null,
    });
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [], sends: [] });
    const execCommand = vi.fn().mockReturnValue(false);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    Object.defineProperty(document, "execCommand", { configurable: true, value: execCommand });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));

    await waitFor(() => expect(screen.getByDisplayValue(shareUrl)).toBeInTheDocument());
    expect(execCommand).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLinkAction }));
    await waitFor(() => expect(execCommand).toHaveBeenCalledWith("copy"));
    expect(await screen.findByText(messages.Delivery.linkCopyFailed)).toBeInTheDocument();
    expect(screen.queryByText(messages.Delivery.linkCopied)).not.toBeInTheDocument();
  });

  it("revokes an active link and refreshes delivery history", async () => {
    const linkId = "77777777-7777-4777-8777-777777777777";
    const link = {
      id: linkId,
      token: "active-token",
      url: "https://reports.example/r/active-token",
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: false,
      open_count: 1,
    };
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [link], sends: [] });
    const revoke = vi.spyOn(api.showings, "revokeShareLink").mockResolvedValue({
      id: linkId,
      token: link.token,
      url: link.url,
      expires_at: null,
      revoked_at: "2026-08-04T13:00:00Z",
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderWithProviders(<DeliveryPanel showing={showing} />);

    fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));

    await waitFor(() => expect(revoke).toHaveBeenCalledWith(visitId, linkId));
    expect(await screen.findByText("Private report link revoked.")).toBeInTheDocument();
  });

  it("creates a replacement link after a sent report's link was revoked", async () => {
    const sentShowing = { ...showing, status: "sent_to_client" as const };
    const revokedLink = {
      id: "77777777-7777-4777-8777-777777777777",
      token: "revoked-token",
      url: "https://reports.example/r/revoked-token",
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: true,
      open_count: 0,
    };
    const replacementUrl = "https://reports.example/r/replacement-token";
    const replacementLink = {
      ...revokedLink,
      id: "88888888-8888-4888-8888-888888888888",
      token: "replacement-token",
      url: replacementUrl,
      revoked: false,
    };
    const create = vi.spyOn(api.showings, "createShareLink").mockResolvedValue({
      id: replacementLink.id,
      token: replacementLink.token,
      url: replacementUrl,
      expires_at: null,
      revoked_at: null,
    });
    vi.spyOn(api.showings, "delivery")
      .mockResolvedValueOnce({ share_links: [revokedLink], sends: [] })
      .mockResolvedValue({ share_links: [replacementLink], sends: [] });
    const send = vi.spyOn(api.showings, "send");
    const invalidateQueries = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    renderWithProviders(<DeliveryPanel showing={sentShowing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.createReplacementLink }));

    await waitFor(() => expect(create).toHaveBeenCalledWith(visitId));
    expect(send).not.toHaveBeenCalled();
    expect((await screen.findAllByDisplayValue(replacementUrl)).length).toBeGreaterThanOrEqual(1);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["showings"] });
    expect(screen.getAllByDisplayValue(replacementUrl).length).toBeGreaterThanOrEqual(1);
  });

  it("creates a replacement link after a sent report's link expires", async () => {
    const sentShowing = { ...showing, status: "sent_to_client" as const };
    const expiredLink = {
      id: "77777777-7777-4777-8777-777777777777",
      token: "expired-token",
      url: "https://reports.example/r/expired-token",
      created_at: "2026-08-04T12:00:00Z",
      expires_at: "2026-08-04T12:30:00Z",
      revoked: false,
      open_count: 0,
    };
    const replacementUrl = "https://reports.example/r/replacement-after-expiry";
    const create = vi.spyOn(api.showings, "createShareLink").mockResolvedValue({
      id: "88888888-8888-4888-8888-888888888888",
      token: "replacement-after-expiry",
      url: replacementUrl,
      expires_at: null,
      revoked_at: null,
    });
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [expiredLink], sends: [] });

    renderWithProviders(<DeliveryPanel showing={sentShowing} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.createReplacementLink }));

    await waitFor(() => expect(create).toHaveBeenCalledWith(visitId));
    expect(await screen.findByDisplayValue(replacementUrl)).toBeInTheDocument();
  });

  it("copies each active link explicitly and leaves a manual URL on copy failure", async () => {
    const link = {
      id: "77777777-7777-4777-8777-777777777777",
      token: "active-token",
      url: "https://reports.example/r/active-token",
      created_at: "2026-08-04T12:00:00Z",
      expires_at: null,
      revoked: false,
      open_count: 1,
    };
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [link], sends: [] });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    const copyButtons = await screen.findAllByRole("button", { name: messages.Delivery.copyLinkAction });
    expect(copyButtons.length).toBeGreaterThanOrEqual(2);
    fireEvent.click(copyButtons[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(link.url));
    expect(await screen.findByText(messages.Delivery.linkCopied)).toBeInTheDocument();

    writeText.mockRejectedValue(new Error("Clipboard unavailable"));
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    Object.defineProperty(document, "execCommand", { configurable: true, value: vi.fn().mockReturnValue(false) });
    fireEvent.click((await screen.findAllByRole("button", { name: messages.Delivery.copyLinkAction }))[0]);

    expect(await screen.findByText(messages.Delivery.linkCopyFailed)).toBeInTheDocument();
    expect(screen.getAllByDisplayValue(link.url).length).toBeGreaterThanOrEqual(2);
  });

  it("rolls active link controls over to expired without navigation", async () => {
    const link = {
      id: "77777777-7777-4777-8777-777777777777",
      token: "soon-expired-token",
      url: "https://reports.example/r/soon-expired-token",
      created_at: "2026-08-04T12:00:00Z",
      expires_at: new Date(Date.now() + 1_000).toISOString(),
      revoked: false,
      open_count: 0,
    };
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [link], sends: [] });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect((await screen.findAllByRole("button", { name: messages.Delivery.copyLinkAction })).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("link", { name: messages.Delivery.openLink })).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole("button", { name: messages.Delivery.copyLinkAction })).not.toBeInTheDocument(), { timeout: 3_000 });
    expect(screen.getByText(messages.Delivery.expired)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: messages.Delivery.openLink })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: messages.Delivery.revokeLink })).not.toBeInTheDocument();
  });

  it("keeps initial confirmed delivery on link_only and never creates by default", async () => {
    const send = vi.spyOn(api.showings, "send").mockResolvedValue({
      send_id: "66666666-6666-4666-8666-666666666666",
      visit_status: "sent_to_client",
      channel: "link_only",
      share_url: "https://reports.example/r/confirmed-token",
      to_email: null,
    });
    const create = vi.spyOn(api.showings, "createShareLink");
    vi.spyOn(api.showings, "delivery").mockResolvedValue({ share_links: [], sends: [] });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderWithProviders(<DeliveryPanel showing={showing} />);

    expect(create).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: messages.Delivery.copyLink }));

    await waitFor(() => expect(send).toHaveBeenCalledWith(visitId, { channel: "link_only" }));
    expect(create).not.toHaveBeenCalled();
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
