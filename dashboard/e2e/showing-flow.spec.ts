import { expect, test } from "@playwright/test";

const visitId = "11111111-1111-4111-8111-111111111111";
const propertyId = "22222222-2222-4222-8222-222222222222";
const observationId = "33333333-3333-4333-8333-333333333333";
const reportId = "44444444-4444-4444-8444-444444444444";
const zoneId = "55555555-5555-4555-8555-555555555555";

test("signup, upload, confirm, and create a share link", async ({ page, context }) => {
  let confirmed = false;
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("https://storage.test/upload/**", (route) =>
    route.fulfill({ status: 200, body: "" }),
  );
  await page.route("**/api/backend/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/backend", "");
    const now = "2026-08-04T10:00:00Z";
    const property = { id: propertyId, display_name: "42 Pipeline Avenue", address: "42 Pipeline Avenue", attributes: {}, created_at: now, updated_at: now };
    const currentVisitId = path.match(/^\/showings\/([^/]+)$/)?.[1] ?? visitId;
    const summary = { id: currentVisitId, status: confirmed ? "confirmed" : "draft", processing_status: "ready", processing_failed_step: null, processing_error: null, started_at: now, ended_at: now, created_at: now, updated_at: now, property, contact: null };
    if (path === "/verticals/real_estate") return route.fulfill({ json: { slug: "real_estate", zone_taxonomy: ["kitchen"], observation_schema: ["light"], display_labels: { zones: { kitchen: "Kitchen" }, observations: { light: "Light" } } } });
    if (/^\/showings\/[^/]+$/.test(path) && route.request().method() === "GET") return route.fulfill({ json: { ...summary, media: [], zones: [{ id: zoneId, zone_type: "kitchen", position: 0, start_transcript_segment_id: null, end_transcript_segment_id: null }], observations: [{ id: observationId, zone_id: zoneId, category: "light", content: "Strong natural light.", source_type: "ai_generated", source_transcript_segment_id: null, source_media_id: null, timestamp_start: null, timestamp_end: null, ai_model: "fake", prompt_version: "test", confidence: 0.9, flags: {}, review_status: "confirmed", reviewed_by: propertyId, reviewed_at: now }], transcript: [], report: { id: reportId, template_id: "real_estate_v1", status: confirmed ? "confirmed" : "pending_review", rendered_html: confirmed ? "<p>Report</p>" : null, content: { executive_summary: "Bright kitchen.", room_by_room: [{ zone_id: zoneId, zone_type: "kitchen", bullets: [{ text: "Strong natural light.", observation_ids: [observationId] }] }], highlights: [{ text: "Strong natural light.", observation_ids: [observationId] }], concerns: [], follow_ups: [] } } } });
    if (path === `/reports/${reportId}`) return route.fulfill({ json: { id: reportId, template_id: "real_estate_v1", status: "pending_review", rendered_html: null, content: (await route.request().postDataJSON()).content } });
    if (/^\/showings\/[^/]+\/confirm$/.test(path)) { confirmed = true; return route.fulfill({ json: { visit_id: path.split("/")[2], report_id: reportId, visit_status: "confirmed", report_status: "confirmed" } }); }
    if (/^\/showings\/[^/]+\/share-links$/.test(path)) return route.fulfill({ json: { id: propertyId, token: "share-token", url: "http://127.0.0.1:8000/r/share-token", expires_at: null, revoked_at: null } });
    return route.continue();
  });

  await page.goto("/signup");
  await page.getByLabel("Email address").fill("agent@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Showing reports" })).toBeVisible();
  await page.getByRole("link", { name: "New showing" }).first().click();
  await page.getByPlaceholder("Start typing an address or property name").fill("42 Pipeline Avenue");
  await page.locator('input[type="file"]').setInputFiles({ name: "showing.m4a", mimeType: "audio/mp4", buffer: Buffer.from("fake-audio") });
  await page.getByRole("button", { name: "Upload and process" }).click();
  await expect(page.getByRole("heading", { name: "42 Pipeline Avenue" })).toBeVisible();
  await page.getByTestId("confirm-button").click();
  await expect(page.getByRole("heading", { name: "Send the confirmed report" })).toBeVisible();
  await page.getByRole("button", { name: "Create and copy link" }).click();
  await expect(page.getByText("Private report link copied.")).toBeVisible();
});
