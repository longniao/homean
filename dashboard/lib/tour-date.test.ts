import { describe, expect, it } from "vitest";

import { tourDate } from "@/lib/tour-date";

describe("tourDate", () => {
  it("uses when the tour happened, not when the row reached the server", () => {
    // Captured offline on Monday, synced on Wednesday.
    const showing = { started_at: "2026-08-10T17:00:00Z", created_at: "2026-08-12T09:00:00Z" };

    expect(tourDate(showing).toISOString()).toBe("2026-08-10T17:00:00.000Z");
  });

  it("falls back to insertion for rows captured before start times were sent", () => {
    const showing = { started_at: null, created_at: "2026-08-12T09:00:00Z" };

    expect(tourDate(showing).toISOString()).toBe("2026-08-12T09:00:00.000Z");
  });
});
