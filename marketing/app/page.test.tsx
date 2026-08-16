import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./page";
import { metadata } from "./layout";
import { pilotMailto, siteConfig } from "@/lib/config";

describe("marketing home page", () => {
  it("offers the pilot CTA and authenticated app link", () => {
    render(<HomePage />);

    expect(screen.getAllByRole("link", { name: /request pilot access/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /sign in/i })[0]).toHaveAttribute("href", siteConfig.appUrl);
    expect(screen.getAllByRole("link", { name: /request pilot access/i })[0]).toHaveAttribute("href", pilotMailto());
  });

  it("states the agent confirmation and private-by-default boundaries", () => {
    render(<HomePage />);

    expect(screen.getAllByText(/nothing is delivered without your explicit confirmation/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/private by default/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/fictional sample · 1840 alder lane/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/no web form or account is created here/i)).toBeInTheDocument();
  });

  it("keeps navigation anchors and high-confidence FAQ content present", () => {
    render(<HomePage />);

    const navigation = within(screen.getByRole("navigation"));
    expect(navigation.getByRole("link", { name: /how it works/i })).toHaveAttribute("href", "#how-it-works");
    expect(navigation.getByRole("link", { name: /for agents/i })).toHaveAttribute("href", "#for-agents");
    expect(navigation.getByRole("link", { name: /trust/i })).toHaveAttribute("href", "#trust");
    expect(screen.getByText(/what happens without connectivity/i)).toBeInTheDocument();
  });

  it("provides a keyboard skip link and stable main landmark", () => {
    render(<HomePage />);

    expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("keeps social metadata on the supported PNG preview and gates indexing", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
    expect(metadata.openGraph?.images).toEqual([
      { url: "/og.png", width: 1200, height: 630, alt: "Homean showing records for buyer’s agents" },
    ]);
    expect(metadata.twitter?.images).toEqual(["/og.png"]);
  });
});
