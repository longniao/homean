// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import worker from "./worker";
const setup = () => {
  const run = vi.fn(async () => ({ success: true }));
  const bind = vi.fn(() => ({ run }));
  return { MARKETING_METRICS: { prepare: vi.fn(() => ({ bind })) }, bind, run, ASSETS: { fetch: vi.fn(async () => new Response("asset")) } };
};
const request = (query: string, origin = "https://homean.com") => new Request(`https://homean.com/_events?${query}`, { method: "POST", headers: { Origin: origin } });
describe("marketing measurement boundary", () => {
  it("counts tool discovery and fictional example activity separately", async () => {
    const env = setup();
    for (const event of ["comparison_tool_click", "comparison_example", "print_comparison_example"]) {
      expect((await worker.fetch(request(`event=${event}&path=/&source=direct`), env as unknown as Env)).status).toBe(204);
      expect(env.bind).toHaveBeenLastCalledWith(event, "/", "direct");
    }
  });
  it("records only allowlisted aggregate dimensions", async () => {
    const env = setup();
    const response = await worker.fetch(request("event=page_view&path=/&source=chatgpt"), env as unknown as Env);
    expect(response.status).toBe(204);
    expect(env.bind).toHaveBeenCalledWith("page_view", "/", "chatgpt");
    expect(env.run).toHaveBeenCalledOnce();
  });
  it("rejects foreign origins, private paths, arbitrary sources, and extra fields", async () => {
    const env = setup();
    for (const req of [request("event=page_view&path=/&source=direct", "https://example.com"), request("event=page_view&path=/clients/private&source=direct"), request("event=page_view&path=/&source=person@example.com"), request("event=page_view&path=/&source=direct&email=person")]) {
      expect((await worker.fetch(req, env as unknown as Env)).status).toBeGreaterThanOrEqual(400);
    }
    expect(env.MARKETING_METRICS.prepare).not.toHaveBeenCalled();
  });
  it("keeps preview domains out of indexes while serving assets", async () => {
    const env = setup();
    const response = await worker.fetch(new Request("https://homean-marketing.longniao.workers.dev/resources/"), env as unknown as Env);
    expect(response.headers.get("X-Robots-Tag")).toBe("noindex, nofollow");
    expect(await response.text()).toBe("asset");
  });
});
