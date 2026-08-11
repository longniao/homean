import { afterEach, describe, expect, it, vi } from "vitest";

import { api, listAllShowings, type Showing } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("showings API client", () => {
  it("forwards the recording consent acknowledgement when creating a showing", async () => {
    const showing = makeShowing("16161616-1616-4616-8616-161616161616");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(showing), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.showings.create({ contact_id: null, consent_ack: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/showings",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ contact_id: null, consent_ack: true }),
      }),
    );
  });

  it("forwards the cursor as the backend cursor query parameter", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.showings.list({ cursor: "cursor-token", limit: 25 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/showings?cursor=cursor-token&limit=25",
      expect.anything(),
    );
  });

  it("loads every showing page with filters and preserves first-seen id deduplication", async () => {
    const first = makeShowing("17171717-1717-4717-8717-171717171717");
    const second = makeShowing("18181818-1818-4818-8818-181818181818");
    const duplicate = { ...first };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [first], next_cursor: "cursor-1" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [duplicate, second], next_cursor: null })));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listAllShowings({ contactId: "19191919-1919-4919-8919-191919191919", status: "confirmed", cursor: "start" });

    expect(result.items.map((showing) => showing.id)).toEqual([first.id, second.id]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/backend/showings?status=confirmed&contact_id=19191919-1919-4919-8919-191919191919&cursor=start&limit=100");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/backend/showings?status=confirmed&contact_id=19191919-1919-4919-8919-191919191919&cursor=cursor-1&limit=100");
  });

  it("rejects on a repeated cursor without making an unbounded request", async () => {
    const first = makeShowing("17171717-1717-4717-8717-171717171717");
    const second = makeShowing("18181818-1818-4818-8818-181818181818");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [first], next_cursor: "cursor-1" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [second], next_cursor: "cursor-1" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listAllShowings({ contactId: "19191919-1919-4919-8919-191919191919", cursor: "start" })).rejects.toThrow(
      "Repeated showing pagination cursor: cursor-1",
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/backend/showings?contact_id=19191919-1919-4919-8919-191919191919&cursor=cursor-1&limit=100");
  });
});

function makeShowing(id: string): Showing {
  return {
    id,
    status: "confirmed",
    processing_status: "ready",
    processing_failed_step: null,
    processing_error: null,
    started_at: "2026-08-05T10:00:00Z",
    ended_at: "2026-08-05T11:00:00Z",
    created_at: "2026-08-05T10:00:00Z",
    updated_at: "2026-08-05T11:00:00Z",
    property: null,
    contact: null,
  };
}
