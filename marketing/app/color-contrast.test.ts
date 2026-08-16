import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "globals.css"),
  "utf8",
);

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!match) throw new Error(`Missing CSS token --${name}`);
  return match[1];
}

function selectorToken(selector: string): string {
  const match = css.match(new RegExp(`\\.${selector}\\s*\\{[^}]*color:\\s*var\\(--([^)]+)\\)`));
  if (!match) throw new Error(`Missing color token for .${selector}`);
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

describe("editorial palette contrast", () => {
  it("keeps critical normal-text pairings at WCAG AA", () => {
    const pairings = [
      ["clay", "paper"],
      ["muted", "paper"],
      ["ink-soft", "paper"],
      ["field-light", "ink"],
    ] as const;

    for (const [foreground, background] of pairings) {
      expect(contrastRatio(token(foreground), token(background))).toBeGreaterThanOrEqual(4.5);
    }

    const pilotNoteForeground = selectorToken("pilot-note");
    expect(pilotNoteForeground).toBe("field-light");
    expect(contrastRatio(token(pilotNoteForeground), token("ink"))).toBeGreaterThanOrEqual(4.5);
  });
});
