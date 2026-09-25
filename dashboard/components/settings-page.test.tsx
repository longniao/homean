import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "@/components/settings-page";
import { ToastProvider } from "@/components/toast-provider";
import { api } from "@/lib/api";
import messages from "@/messages/en.json";

const uuid = "11111111-1111-4111-8111-111111111111";
const me = {
  user: { id: uuid, email: "agent@example.com", name: "Agent", phone: null },
  workspace: { id: uuid, name: "Workspace", language: "en" },
  profile: { id: uuid, role: "buyers_agent", vertical: "real_estate" },
};
const branding = {
  id: null,
  logo_key: null,
  display_name: null,
  phone: null,
  email: null,
  license_no: null,
  accent_color: "#1F6F5B",
  updated_at: null,
};

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <SettingsPage />
        </ToastProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Settings billing action", () => {
  it.each([
    ["active trial", { plan: "trial", status: "trialing", active: true, billing_action: "subscribe", can_checkout: true, can_portal: false, stripe_customer_attached: false }, "Subscribe", "checkout"],
    ["active paid", { plan: "solo_monthly", status: "active", active: true, billing_action: "manage_billing", can_checkout: false, can_portal: true, stripe_customer_attached: true }, "Manage billing", "portal"],
    ["canceled paid customer", { plan: "solo_monthly", status: "canceled", active: false, billing_action: "subscribe", can_checkout: true, can_portal: true, stripe_customer_attached: true }, "Subscribe", "checkout"],
    ["expired trial", { plan: "trial", status: "trialing", active: false, billing_action: "subscribe", can_checkout: true, can_portal: false, stripe_customer_attached: false }, "Subscribe", "checkout"],
  ] as const)("uses the correct Stripe path for %s", async (_state, status, label, method) => {
    vi.spyOn(api, "me").mockResolvedValue(me);
    vi.spyOn(api.branding, "get").mockResolvedValue(branding);
    vi.spyOn(api.branding, "preview").mockResolvedValue("<html></html>");
    vi.spyOn(api.billing, "get").mockResolvedValue({
      workspace_id: uuid,
      plan: status.plan,
      status: status.status,
      active: status.active,
      billing_action: status.billing_action,
      can_checkout: status.can_checkout,
      can_portal: status.can_portal,
      stripe_customer_attached: status.stripe_customer_attached,
      trial_ends_at: null,
      current_period_end: null,
      cancel_at_period_end: false,
    });
    const action = vi.spyOn(api.billing, method).mockRejectedValue(
      new Error("test redirect"),
    );

    renderSettings();
    const button = await screen.findByRole("button", { name: label });
    fireEvent.click(button);
    await waitFor(() => expect(action).toHaveBeenCalledTimes(1));
  });
});

describe("Settings account deletion", () => {
  function mockAccount() {
    vi.spyOn(api, "me").mockResolvedValue(me);
    vi.spyOn(api.branding, "get").mockResolvedValue(branding);
    vi.spyOn(api.branding, "preview").mockResolvedValue("<html></html>");
    vi.spyOn(api.billing, "get").mockResolvedValue({
      workspace_id: uuid, plan: "trial", status: "trialing", active: true, billing_action: "subscribe",
      can_checkout: true, can_portal: false, stripe_customer_attached: false,
      trial_ends_at: null, current_period_end: null, cancel_at_period_end: false,
    });
  }

  it("asks for the password, confirms, then deletes and signs out", async () => {
    mockAccount();
    const deleteAccount = vi.spyOn(api, "deleteAccount").mockResolvedValue(null);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });

    renderSettings();
    const password = await screen.findByLabelText("Confirm your password");
    const trigger = screen.getByRole("button", { name: "Delete my account" });
    expect(trigger).toBeDisabled();
    fireEvent.change(password, { target: { value: "correct-horse-battery" } });
    fireEvent.click(trigger);
    expect(deleteAccount).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: "Yes, delete everything" }));
    await waitFor(() => expect(deleteAccount).toHaveBeenCalledWith("correct-horse-battery"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
    vi.unstubAllGlobals();
  });

  it("keeps the account and explains a wrong password", async () => {
    mockAccount();
    const { ApiError } = await import("@/lib/api");
    vi.spyOn(api, "deleteAccount").mockRejectedValue(new ApiError(403, "Password does not match", null));
    const fetchMock = vi.spyOn(globalThis, "fetch");

    renderSettings();
    fireEvent.change(await screen.findByLabelText("Confirm your password"), { target: { value: "wrong-password-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Yes, delete everything" }));
    expect(await screen.findByText("That password does not match.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/auth/logout", expect.anything());
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeTruthy();
  });
});
