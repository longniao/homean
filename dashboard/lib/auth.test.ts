import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ACCESS_COOKIE,
  ACCESS_COOKIE_NAMES,
  backendUrl,
  LEGACY_ACCESS_COOKIE,
  LEGACY_REFRESH_COOKIE,
  REFRESH_COOKIE,
  REFRESH_COOKIE_NAMES,
} from "./auth";

afterEach(() => vi.unstubAllEnvs());

describe("Homean auth cookie compatibility", () => {
  it("writes Homean cookies while recognizing the legacy Kawu names", () => {
    expect(ACCESS_COOKIE).toBe("homean_access");
    expect(REFRESH_COOKIE).toBe("homean_refresh");
    expect(ACCESS_COOKIE_NAMES).toEqual(["homean_access", LEGACY_ACCESS_COOKIE]);
    expect(REFRESH_COOKIE_NAMES).toEqual(["homean_refresh", LEGACY_REFRESH_COOKIE]);
  });

  it("uses the server-only API origin before the legacy public setting", () => {
    vi.stubEnv("HOMEAN_API_URL", "https://api.homean.test/");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://legacy.homean.test");

    expect(backendUrl()).toBe("https://api.homean.test");
  });
});
