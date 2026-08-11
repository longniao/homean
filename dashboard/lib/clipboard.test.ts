import { afterEach, describe, expect, it, vi } from "vitest";

import { copyTextToClipboard } from "@/lib/clipboard";

const originalClipboard = navigator.clipboard;
const originalExecCommand = document.execCommand;

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: originalClipboard,
  });
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: originalExecCommand,
  });
});

describe("copyTextToClipboard", () => {
  it("returns false when selection and focus restoration throw", async () => {
    const activeElement = document.createElement("button");
    document.body.appendChild(activeElement);
    activeElement.focus();

    const selection = {
      rangeCount: 0,
      removeAllRanges: vi.fn(() => {
        throw new Error("selection changed");
      }),
      addRange: vi.fn(),
      getRangeAt: vi.fn(),
    } as unknown as Selection;
    vi.spyOn(document, "getSelection").mockReturnValue(selection);
    vi.spyOn(activeElement, "focus").mockImplementation(() => {
      throw new Error("focus unavailable");
    });
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    Object.defineProperty(document, "execCommand", { configurable: true, value: vi.fn().mockReturnValue(false) });

    await expect(copyTextToClipboard("https://reports.example/r/token")).resolves.toBe(false);
  });
});
