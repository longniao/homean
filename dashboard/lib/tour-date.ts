import type { Showing } from "@/lib/api";

/**
 * When the tour happened, for display.
 *
 * `created_at` is when the row reached the server, which for an offline
 * capture is whenever it next found signal — showing a Monday tour as
 * Wednesday, and contradicting the date its own report prints. Falls back to
 * insertion for rows captured before the client reported a start time.
 */
export function tourDate(showing: Pick<Showing, "started_at" | "created_at">): Date {
  return new Date(showing.started_at ?? showing.created_at);
}
