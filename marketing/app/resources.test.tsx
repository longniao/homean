import { readFileSync } from "node:fs";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ResourcePage, { generateMetadata } from "./resources/[slug]/page";
import ResourcesPage from "./resources/page";
import sitemap from "./sitemap";
import robots from "./robots";
import { resources } from "@/lib/resources";
import { siteConfig } from "@/lib/config";

describe("public discovery resources", () => {
  it("pairs all five template steps with explicitly fictional worked examples", async () => {
    render(await ResourcePage({ params: Promise.resolve({ slug: "showing-report-template" }) }));
    expect(screen.getAllByText("Filled example · fictional")).toHaveLength(5);
    expect(screen.getByText(/confirmation has not been performed/i)).toBeVisible();
    expect(screen.getByText(/not drawn from a listing, customer report, or completed AI trial/i)).toBeVisible();
  });
  it("renders a single index heading and links all resources", () => {
    render(<ResourcesPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const resource of resources) expect(screen.getByRole("link", { name: resource.title })).toHaveAttribute("href", `/resources/${resource.slug}`);
  });
  it("makes the example clearly fictional and printable", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(await ResourcePage({ params: Promise.resolve({ slug: "sample-showing-report" }) }));
    expect(screen.getByText(/every property detail and buyer preference below is invented/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /print or save as pdf/i }));
    expect(print).toHaveBeenCalledOnce();
    print.mockRestore();
  });
  it("provides complete editable templates without requiring an account", () => {
    for (const resource of resources.filter(item => item.download)) {
      const text = readFileSync(`public${resource.download}`, "utf8");
      expect(text).toContain("Keep completed copies private");
      expect(text.length).toBeGreaterThan(500);
    }
  });
  it("has unique canonicals and a sitemap containing only public pages", async () => {
    for (const resource of resources) {
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: resource.slug }) });
      expect(metadata.alternates?.canonical).toBe(`/resources/${resource.slug}/`);
      expect(metadata.title).toContain(resource.title);
    }
    const urls = sitemap().map(item => item.url);
    expect(new Set(urls).size).toBe(8);
    expect(urls.some(url => /\/reports?\/|\/clients?\/|signup/.test(url))).toBe(false);
  });
  it("permits search indexing only when enabled, independently of training", () => {
    const previous = siteConfig.indexable;
    Object.assign(siteConfig, { indexable: true });
    expect(robots().rules).toEqual(expect.arrayContaining([
      { userAgent: "OAI-SearchBot", allow: "/", disallow: "/_events" },
      { userAgent: "GPTBot", disallow: "/" },
    ]));
    Object.assign(siteConfig, { indexable: previous });
  });
});
