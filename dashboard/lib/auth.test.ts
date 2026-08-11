import { describe, expect, it } from "vitest";

import {
  ACCESS_COOKIE,
  ACCESS_COOKIE_NAMES,
  LEGACY_ACCESS_COOKIE,
  LEGACY_REFRESH_COOKIE,
  REFRESH_COOKIE,
  REFRESH_COOKIE_NAMES,
} from "./auth";

describe("Homean auth cookie compatibility", () => {
  it("writes Homean cookies while recognizing the legacy Kawu names", () => {
    expect(ACCESS_COOKIE).toBe("homean_access");
    expect(REFRESH_COOKIE).toBe("homean_refresh");
    expect(ACCESS_COOKIE_NAMES).toEqual(["homean_access", LEGACY_ACCESS_COOKIE]);
    expect(REFRESH_COOKIE_NAMES).toEqual(["homean_refresh", LEGACY_REFRESH_COOKIE]);
  });
});
