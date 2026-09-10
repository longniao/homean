import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HomeComparison } from "./home-comparison";
function fillHome(number: number, name: string, note?: string) {
  const group = within(screen.getByRole("group", { name: `Home ${number}` }));
  fireEvent.change(group.getByRole("textbox", { name: "Name or nickname" }), { target: { value: name } });
  if (note) fireEvent.change(group.getByRole("textbox", { name: "What stood out" }), { target: { value: note } });
}
describe("private home comparison", () => {
  it("shows a fictional example without overwriting or mixing in personal notes", () => {
    render(<HomeComparison />);
    fillHome(1, "My private home", "My private note");
    fireEvent.change(screen.getByRole("textbox", { name: "Our shared priorities" }), { target: { value: "My priorities" } });
    fireEvent.click(screen.getByRole("button", { name: /see a filled example/i }));
    expect(screen.getByText(/fictional example — not real listings/i)).toBeVisible();
    const table = within(screen.getByRole("table"));
    expect(table.getAllByRole("columnheader")).toHaveLength(4);
    expect(table.getByRole("columnheader", { name: "Birch Place (fictional)" })).toBeInTheDocument();
    expect(table.queryByText("My private note")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Back to my notes" }));
    expect(screen.getByDisplayValue("My private home")).toBeVisible();
    expect(screen.getByDisplayValue("My private note")).toBeVisible();
    expect(screen.getByDisplayValue("My priorities")).toBeVisible();
    expect(screen.getByRole("button", { name: /compare homes/i })).toBeDisabled();
  });
  it("keeps example printing identifiable and separate from personal comparison metrics", () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<HomeComparison />);
    fireEvent.click(screen.getByRole("button", { name: /see a filled example/i }));
    const label = screen.getByText(/fictional example — not real listings/i);
    expect(label.closest(".no-print")).toBeNull();
    const button = screen.getByRole("button", { name: "Print example" });
    expect(button).toHaveAttribute("data-measure", "print_comparison_example");
    fireEvent.click(button);
    expect(print).toHaveBeenCalledOnce();
    print.mockRestore();
  });
  it("requires two names, preserves differences, and labels missing information", () => {
    render(<HomeComparison />);
    const compare = screen.getByRole("button", { name: /compare homes/i });
    expect(compare).toBeDisabled();
    fillHome(1, "Alder", "Quiet rear room\nAfternoon visit");
    expect(compare).toBeDisabled();
    fillHome(2, "Cedar", "<script>fictional note</script>");
    fireEvent.click(compare);
    const table = within(screen.getByRole("table"));
    expect(table.getByRole("columnheader", { name: "Alder" })).toBeInTheDocument();
    expect(table.getByRole("columnheader", { name: "Cedar" })).toBeInTheDocument();
    expect(table.getByText(/Quiet rear room/)).toBeInTheDocument();
    expect(table.getByText("<script>fictional note</script>")).toBeInTheDocument();
    expect(table.getAllByText("Not recorded — ask or assess").length).toBeGreaterThan(0);
    expect(table.queryByRole("columnheader", { name: "Home 3" })).toBeNull();
  });
  it("keeps notes for an unnamed third home in the comparison", () => {
    render(<HomeComparison />); fillHome(1, "Alder"); fillHome(2, "Cedar");
    const third = within(screen.getByRole("group", { name: "Home 3" }));
    fireEvent.change(third.getByRole("textbox", { name: "What stood out" }), { target: { value: "Third home's notes" } });
    fireEvent.click(screen.getByRole("button", { name: /compare homes/i }));
    expect(screen.getByRole("columnheader", { name: "Home 3" })).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Third home's notes")).toBeInTheDocument();
  });
  it("retains edits and clears only after an explicit clear action", () => {
    render(<HomeComparison />);
    fillHome(1, "Alder"); fillHome(2, "Cedar");
    fireEvent.click(screen.getByRole("button", { name: /compare homes/i }));
    fireEvent.click(screen.getByRole("button", { name: "Edit notes" }));
    expect(screen.getByDisplayValue("Alder")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear all notes" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep notes" }));
    expect(screen.getByDisplayValue("Alder")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear all notes" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, clear notes" }));
    expect(screen.queryByDisplayValue("Alder")).toBeNull();
    expect(screen.getByRole("button", { name: /compare homes/i })).toBeDisabled();
  });
  it("prints entered notes without sending them and does not persist them on remount", () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    const fetch = vi.spyOn(globalThis, "fetch");
    const first = render(<HomeComparison />);
    fillHome(1, "Private nickname"); fillHome(2, "Second home");
    fireEvent.click(screen.getByRole("button", { name: /compare homes/i }));
    fireEvent.click(screen.getByRole("button", { name: "Print or save as PDF" }));
    expect(print).toHaveBeenCalledOnce(); expect(fetch).not.toHaveBeenCalled();
    first.unmount(); render(<HomeComparison />);
    expect(screen.queryByDisplayValue("Private nickname")).toBeNull();
    print.mockRestore(); fetch.mockRestore();
  });
});
