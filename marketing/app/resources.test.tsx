import { readFileSync } from "node:fs";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ResourcePage, { generateMetadata } from "./resources/[slug]/page";
import ResourcesPage from "./resources/page";
import sitemap from "./sitemap";
import robots from "./robots";
import { resources } from "@/lib/resources";
import { siteConfig } from "@/lib/config";
import { publicPages, updatedAt } from "@/lib/public-pages";
import { resourceAnswers } from "@/lib/resource-answers";
import { resourceSchema } from "@/lib/discovery";
import AboutPage from "./about/page";

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
    expect(new Set(urls).size).toBe(publicPages.length);
    expect(urls).toContain(`${siteConfig.siteUrl}/about/`);
    expect(urls.some(url => /\/reports?\/|\/clients?\/|signup/.test(url))).toBe(false);
  });
  it("publishes visible answers, attribution and dates for every guide", async () => {
    for (const resource of resources) {
      const { container, unmount } = render(await ResourcePage({ params: Promise.resolve({ slug: resource.slug }) }));
      const answers = resourceAnswers[resource.slug];
      expect(screen.getByRole("heading", { name: answers.question })).toBeVisible();
      for (const answer of answers.questions) {
        expect(screen.getByRole("heading", { name: answer.question })).toBeVisible();
        expect(screen.getByText(answer.answer)).toBeVisible();
      }
      expect(screen.getByRole("link", { name: "Homean" })).toHaveAttribute("href", "/about");
      expect(container.querySelector("time")?.dateTime).toBe(updatedAt(`/resources/${resource.slug}/`));
      for (const link of container.querySelectorAll('a[href^="#"]')) {
        expect(container.querySelector(link.getAttribute("href")!)).not.toBeNull();
      }
      expect(resources.some(item => item.slug === answers.nextSlug)).toBe(true);
      const schema = JSON.parse(container.querySelector('script[type="application/ld+json"]')!.textContent!);
      expect(schema).toEqual(resourceSchema(resource));
      expect(schema["@graph"][0].dateModified).toBe(container.querySelector("time")?.dateTime);
      expect(schema["@graph"][1].itemListElement.map((item: { name: string }) => item.name))
        .toEqual(["Home", "Free resources", resource.title]);
      unmount();
    }
  });
  it("explains editorial provenance without inventing reviewers or live availability", () => {
    render(<AboutPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText(/No named professional reviewer or customer endorsement is claimed/)).toBeVisible();
    expect(screen.getByText(/not announced as ready for live-client use/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Check current product availability →" })).toHaveAttribute("href", "/how-it-works");
  });
  it("uses article social metadata and keeps editorial dates consistent with sitemap", async () => {
    for (const resource of resources) {
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: resource.slug }) });
      expect(metadata.openGraph).toMatchObject({ type: "article", modifiedTime: updatedAt(`/resources/${resource.slug}/`) });
      const entry = sitemap().find(item => item.url === `${siteConfig.siteUrl}/resources/${resource.slug}/`);
      expect(entry?.lastModified).toEqual(new Date(updatedAt(`/resources/${resource.slug}/`)));
    }
    expect(() => updatedAt("/private-report/")).toThrow();
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
