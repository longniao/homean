export async function copyTextToClipboard(value: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Some browsers expose Clipboard API but reject it outside a secure context.
  }

  if (typeof document === "undefined") return false;

  const activeElement = document.activeElement as HTMLElement | null;
  const selection = document.getSelection();
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, index) =>
        selection.getRangeAt(index),
      )
    : [];
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  textarea.tabIndex = -1;
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  textarea.style.opacity = "0";

  try {
    document.body.appendChild(textarea);
    textarea.focus({ preventScroll: true });
    textarea.select();
    return typeof document.execCommand === "function" && document.execCommand("copy");
  } catch {
    return false;
  } finally {
    try {
      textarea.remove();
    } catch {
      // Cleanup must never turn a failed copy into a rejected promise.
    }
    try {
      selection?.removeAllRanges();
      ranges.forEach((range) => selection?.addRange(range));
    } catch {
      // A browser may invalidate the saved selection while the textarea is focused.
    }
    try {
      activeElement?.focus({ preventScroll: true });
    } catch {
      // Focus restoration is best effort and must not change the boolean result.
    }
  }
}
