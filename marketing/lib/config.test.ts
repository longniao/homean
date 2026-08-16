import { describe, expect, it } from "vitest";

import { parsePublicConfig } from "@/lib/config";

const validInput = {
  NEXT_PUBLIC_SITE_URL: "https://marketing.invalid",
  NEXT_PUBLIC_APP_URL: "https://app.invalid",
  NEXT_PUBLIC_PILOT_EMAIL: "pilot@marketing.invalid",
};

describe("public production configuration", () => {
  it("accepts valid URLs and pilot email", () => {
    expect(parsePublicConfig(validInput, { production: true })).toEqual({
      siteUrl: "https://marketing.invalid",
      appUrl: "https://app.invalid",
      pilotEmail: "pilot@marketing.invalid",
    });
  });

  it("fails when required production values are missing", () => {
    expect(() => parsePublicConfig({}, { production: true })).toThrow(
      "Missing required production configuration: NEXT_PUBLIC_SITE_URL",
    );
  });

  it("fails when a URL or email is invalid", () => {
    expect(() =>
      parsePublicConfig(
        { ...validInput, NEXT_PUBLIC_SITE_URL: "homean.invalid" },
        { production: true },
      ),
    ).toThrow("Invalid URL for NEXT_PUBLIC_SITE_URL");

    expect(() =>
      parsePublicConfig(
        { ...validInput, NEXT_PUBLIC_PILOT_EMAIL: "pilot-at-invalid" },
        { production: true },
      ),
    ).toThrow("Invalid email for NEXT_PUBLIC_PILOT_EMAIL");
  });

  it("uses local-only defaults outside production", () => {
    expect(parsePublicConfig({}, { production: false })).toEqual({
      siteUrl: "http://localhost:3000",
      appUrl: "http://localhost:3001",
      pilotEmail: "pilot@example.invalid",
    });
  });
});
