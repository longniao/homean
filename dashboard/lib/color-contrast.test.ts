import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../app/globals.css"),
  "utf8",
);

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!match) throw new Error(`Missing CSS token --${name}`);
  return match[1];
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map(
    (offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255,
  );
  const linear = channels.map((channel) =>
    channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(foreground: string, background: string): number {
  const [bright, dark] = [luminance(foreground), luminance(background)].sort(
    (a, b) => b - a,
  );
  return (bright + 0.05) / (dark + 0.05);
}

describe("shared Homean palette contrast", () => {
  it("keeps application text and actions at WCAG AA", () => {
    const pairings = [
      ["foreground", "background"],
      ["card-foreground", "card"],
      ["primary-foreground", "primary"],
      ["muted-foreground", "muted"],
      ["accent-foreground", "accent"],
      ["sidebar-foreground", "sidebar"],
    ] as const;

    for (const [foreground, background] of pairings) {
      expect(contrastRatio(token(foreground), token(background))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the shared slash mark visible on its dark tile", () => {
    expect(contrastRatio("#a5b4fc", "#0d1117")).toBeGreaterThanOrEqual(4.5);
  });
});
