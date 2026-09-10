const paths = new Set(["/", "/how-it-works/", "/resources/", "/resources/showing-report-template/", "/resources/sample-showing-report/", "/resources/home-comparison-worksheet/", "/resources/how-to-compare-homes-after-touring/", "/resources/what-to-write-after-a-showing/"]);
const events = new Set(["page_view", "signup_click", "print_resource", "download_resource", "comparison_view", "print_comparison"]);
const sources = new Set(["direct", "google", "bing", "chatgpt", "other", "internal"]);

export default {
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);
    if (url.pathname === "/_events") {
      const headers = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex" };
      if (request.method !== "POST") return new Response(null, { status: 405, headers });
      if (url.hostname !== "homean.com" || request.headers.get("Origin") !== "https://homean.com") return new Response(null, { status: 403, headers });
      const event = url.searchParams.get("event") ?? "";
      const path = url.searchParams.get("path") ?? "";
      const source = url.searchParams.get("source") ?? "";
      if (url.search.length > 250 || [...url.searchParams.keys()].some(key => !["event", "path", "source"].includes(key)) || !events.has(event) || !paths.has(path) || !sources.has(source)) return new Response(null, { status: 400, headers });
      try {
        await env.MARKETING_METRICS.prepare(
          "INSERT INTO daily_metrics(day,event,path,source,total) VALUES(date('now'),?1,?2,?3,1) ON CONFLICT(day,event,path,source) DO UPDATE SET total=total+1"
        ).bind(event, path, source).run();
      } catch {
        return new Response(null, { status: 503, headers });
      }
      return new Response(null, { status: 204, headers });
    }
    const response = await env.ASSETS.fetch(request);
    if (url.hostname === "homean.com") return response;
    const headers = new Headers(response.headers);
    headers.set("X-Robots-Tag", "noindex, nofollow");
    return new Response(response.body, { status: response.status, headers });
  },
} satisfies ExportedHandler<Env>;
