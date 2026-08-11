import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, uploadWithProgress: vi.fn().mockResolvedValue(undefined) };
});

import { NewShowingForm } from "@/components/new-showing-form";
import { ToastProvider } from "@/components/toast-provider";
import { api, type Property, type Showing } from "@/lib/api";
import messages from "@/messages/en.json";

const showingId = "11111111-1111-4111-8111-111111111111";
const propertyId = "22222222-2222-4222-8222-222222222222";
const mediaId = "33333333-3333-4333-8333-333333333333";

const savedProperty: Property = {
  id: propertyId,
  display_name: "Maple Street Home",
  address: "123 Maple Street",
  attributes: {},
  created_at: "2026-08-05T10:00:00Z",
  updated_at: "2026-08-05T10:00:00Z",
};

const showing: Showing = {
  id: showingId,
  status: "draft",
  processing_status: "not_started",
  processing_failed_step: null,
  processing_error: null,
  started_at: "2026-08-05T10:00:00Z",
  ended_at: null,
  created_at: "2026-08-05T10:00:00Z",
  updated_at: "2026-08-05T10:00:00Z",
  property: null,
  contact: null,
};

function renderForm(properties: Property[] = []) {
  vi.spyOn(api.properties, "list").mockResolvedValue(properties);
  vi.spyOn(api.contacts, "list").mockResolvedValue([]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider><NewShowingForm /></ToastProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

function mockUpload() {
  vi.spyOn(api.showings, "create").mockResolvedValue(showing);
  vi.spyOn(api.showings, "presign").mockResolvedValue({
    media_id: mediaId,
    upload_url: "https://storage.test/upload/audio",
    method: "PUT",
    headers: {},
    expires_in: 300,
    max_size_bytes: 10_000_000,
  });
  vi.spyOn(api.showings, "complete").mockResolvedValue({
    id: mediaId,
    type: "audio",
    content_type: "audio/mp4",
    timestamp_offset_ms: null,
    status: "completed",
    size_bytes: 10,
    created_at: "2026-08-05T10:00:00Z",
  });
  vi.spyOn(api.showings, "finish").mockResolvedValue({});
}

function addAudio() {
  fireEvent.change(screen.getByLabelText("Choose files"), {
    target: { files: [new File(["audio"], "showing.m4a", { type: "audio/mp4" })] },
  });
}

function acknowledgeConsent() {
  fireEvent.click(screen.getByRole("checkbox", { name: "I attest that I have consent to record this showing" }));
}

afterEach(() => vi.restoreAllMocks());
beforeEach(() => push.mockClear());

describe("NewShowingForm property selection", () => {
  it("requires an explicit property choice when the assigned path is empty", async () => {
    mockUpload();
    renderForm();
    addAudio();
    acknowledgeConsent();

    fireEvent.click(screen.getByRole("button", { name: "Upload and process" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Choose a property or select No property yet.",
    );
    expect(api.showings.create).not.toHaveBeenCalled();
  });

  it("creates a showing without subject or client when No property yet is selected", async () => {
    mockUpload();
    renderForm();

    fireEvent.click(screen.getByRole("radio", { name: /No property yet/ }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "created without a property or address",
    );
    addAudio();
    acknowledgeConsent();
    fireEvent.click(screen.getByRole("button", { name: "Upload and process" }));

    await waitFor(() =>
      expect(api.showings.create).toHaveBeenCalledWith({ contact_id: null, consent_ack: true }),
    );
    expect(api.showings.presign).toHaveBeenCalledWith(showingId, {
      type: "audio",
      content_type: "audio/mp4",
    });
    expect(push).toHaveBeenCalledWith(`/showings/${showingId}`);
  });

  it("keeps saved-property selection intact", async () => {
    mockUpload();
    renderForm([savedProperty]);
    await waitFor(() => expect(api.properties.list).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText("Start typing an address or property name"), {
      target: { value: "Maple" },
    });
    await waitFor(() => expect(screen.getByRole("button", { name: /Maple Street Home/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Maple Street Home/ }));
    addAudio();
    acknowledgeConsent();
    fireEvent.click(screen.getByRole("button", { name: "Upload and process" }));
    await waitFor(() =>
      expect(api.showings.create).toHaveBeenCalledWith({
        subject_id: propertyId,
        contact_id: null,
        consent_ack: true,
      }),
    );
  });

  it("keeps new-address creation intact", async () => {
    mockUpload();
    renderForm();
    fireEvent.change(screen.getByPlaceholderText("Start typing an address or property name"), {
      target: { value: "89 Silent Street" },
    });
    addAudio();
    acknowledgeConsent();
    fireEvent.click(screen.getByRole("button", { name: "Upload and process" }));
    await waitFor(() =>
      expect(api.showings.create).toHaveBeenCalledWith({
        address: "89 Silent Street",
        contact_id: null,
        consent_ack: true,
      }),
    );
  });

  it("requires an accessible consent attestation before uploading", async () => {
    mockUpload();
    renderForm();
    fireEvent.click(screen.getByRole("radio", { name: /No property yet/ }));
    addAudio();

    const consent = screen.getByRole("checkbox", { name: "I attest that I have consent to record this showing" });
    expect(consent).toHaveAttribute("aria-describedby", "consent-help");
    expect(screen.getByRole("button", { name: "Upload and process" })).toBeDisabled();
    fireEvent.submit(screen.getByRole("button", { name: "Upload and process" }).closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Confirm that you have consent to record this showing before uploading.",
    );
    expect(api.showings.create).not.toHaveBeenCalled();
  });
});
