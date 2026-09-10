// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "../middleware";
import { PATCH, GET } from "../app/api/backend/[...path]/route";
const { jar } = vi.hoisted(() => ({ jar: new Map<string, string>() }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: (key: string) => jar.has(key) ? { value: jar.get(key) } : undefined }) }));
const params = { params: Promise.resolve({ path: ["reports", "test"] }) };
beforeEach(() => { vi.restoreAllMocks(); jar.clear(); jar.set("homean_refresh", "session"); });
describe("session restoration", () => {
  it("allows a refresh-only session to reach the API on navigation", () => {
    const response = middleware(new NextRequest("http://localhost/showings/test", { headers: { cookie: "homean_refresh=session" } }));
    expect(response.headers.get("location")).toBeNull();
    expect(middleware(new NextRequest("http://localhost/showings/test")).headers.get("location")).toContain("/login");
  });
  it("replays the exact write body after successful refresh", async () => {
    const fetch = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({}, { status: 401 }))
      .mockResolvedValueOnce(Response.json({ access_token: "new", refresh_token: "session", expires_in: 900 }))
      .mockResolvedValueOnce(Response.json({ saved: true }));
    const body = JSON.stringify({ content: "agent edit" });
    const response = await PATCH(new NextRequest("http://localhost/api/backend/reports/test", { method: "PATCH", body }), params);
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(new TextDecoder().decode(fetch.mock.calls[2][1]?.body as ArrayBuffer)).toBe(body);
    expect((fetch.mock.calls[2][1]?.headers as Headers).get("Authorization")).toBe("Bearer new");
  });
  it.each([429, 503])("preserves refresh cookies on transient %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({}, { status: 401 })).mockResolvedValueOnce(Response.json({}, { status }));
    const response = await GET(new NextRequest("http://localhost/api/backend/me"), params);
    expect(response.status).toBe(status);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
  it("preserves refresh cookies on a network error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({}, { status: 401 })).mockRejectedValueOnce(new Error("offline"));
    const response = await GET(new NextRequest("http://localhost/api/backend/me"), params);
    expect(response.status).toBe(503);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
  it.each([401, 403])("clears an explicitly rejected session (%s)", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({}, { status: 401 })).mockResolvedValueOnce(Response.json({}, { status }));
    const response = await GET(new NextRequest("http://localhost/api/backend/me"), params);
    expect(response.cookies.get("homean_refresh")?.value).toBe("");
  });
});

it('returns a retryable unavailable response when the backend cannot be reached', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('DNS lookup failed'));
  const response = await GET(new NextRequest('http://localhost/api/backend/me'), params);
  expect(response.status).toBe(503);
  expect(response.headers.get('set-cookie')).toBeNull();
});
