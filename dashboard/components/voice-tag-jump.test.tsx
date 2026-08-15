import { describe, expect, it } from "vitest";

import type { ShowingDetail } from "@/lib/api";

type Marker = ShowingDetail["markers"][number];

/**
 * Mirrors the filter the transcript tab applies. A tag that resolved to no
 * segment has no evidence to jump to, so offering it as a jump point would
 * produce a control that goes nowhere.
 */
function jumpableTags(markers: Marker[]): Marker[] {
  return markers.filter((marker) => marker.transcript_segment_id !== null);
}

const marker = (id: string, segmentId: string | null): Marker => ({
  id,
  marker_type: "voice_tag",
  timestamp_offset_ms: 1_200,
  transcript_segment_id: segmentId,
  created_at: "2026-08-04T10:00:00Z",
});

describe("voice tag jump points", () => {
  it("offers a jump point for a tag that resolved to evidence", () => {
    const tags = jumpableTags([marker("a", "segment-1")]);

    expect(tags).toHaveLength(1);
    expect(tags[0]!.transcript_segment_id).toBe("segment-1");
  });

  it("omits a tag that bookmarks nothing", () => {
    // Tapped after the last thing said, so it points at no transcript.
    expect(jumpableTags([marker("b", null)])).toHaveLength(0);
  });

  it("keeps only the resolvable tags when a visit has both", () => {
    const tags = jumpableTags([marker("a", "segment-1"), marker("b", null)]);

    expect(tags.map((tag) => tag.id)).toEqual(["a"]);
  });
});
