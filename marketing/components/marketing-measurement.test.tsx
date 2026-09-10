import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarketingMeasurement, referralCategory } from "./marketing-measurement";
vi.mock("next/navigation", () => ({ usePathname: () => "/resources/" }));
describe("public referral measurement", () => {
  it("reduces referrers to categories without retaining URLs", () => {
    expect(referralCategory("https://chatgpt.com/c/private-chat-id", "")).toBe("chatgpt");
    expect(referralCategory("", "?utm_source=chatgpt.com&private=value")).toBe("chatgpt");
    expect(referralCategory("https://www.google.ca/search?q=private", "")).toBe("google");
    expect(referralCategory("https://chatgpt.com.example.org/path", "")).toBe("other");
    expect(referralCategory("", "")).toBe("direct");
  });
  it("does not send development or preview traffic", () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    render(<MarketingMeasurement signupUrl="https://app.homean.com/signup" />);
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockRestore();
  });
});
