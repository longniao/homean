import { expect, test } from "@playwright/test";

const visitId = "11111111-1111-4111-8111-111111111111";
const propertyId = "22222222-2222-4222-8222-222222222222";
const observationId = "33333333-3333-4333-8333-333333333333";
const reportId = "44444444-4444-4444-8444-444444444444";
const zoneId = "55555555-5555-4555-8555-555555555555";
const reportSendId = "66666666-6666-4666-8666-666666666666";
const shareLinkId = "77777777-7777-4777-8777-777777777777";
const shareUrl = "http://127.0.0.1:8000/r/share-token";
const subjectlessVisitId = "88888888-8888-4888-8888-888888888888";
const subjectlessPropertyId = "99999999-9999-4999-8999-999999999999";
const subjectlessObservationId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const subjectlessReportId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const subjectlessZoneId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const subjectlessMediaId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

test("signup, upload, confirm, and deliver a share link", async ({ page, context }) => {
  let status: "draft" | "confirmed" | "sent_to_client" = "draft";
  let sendCount = 0;
  let shareLinkRevoked = false;
  let activeVisitId = visitId;
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
    const summary = { id: currentVisitId, status, processing_status: "ready", processing_failed_step: null, processing_error: null, started_at: now, ended_at: now, created_at: now, updated_at: now, property, contact: null };
    if (/^\/showings\/[^/]+$/.test(path) && route.request().method() === "GET") {
      activeVisitId = currentVisitId;
      return route.fulfill({ json: { ...summary, media: [], zones: [{ id: zoneId, zone_type: "kitchen", position: 0, start_transcript_segment_id: null, end_transcript_segment_id: null }], observations: [{ id: observationId, zone_id: zoneId, category: "light", content: "Strong natural light.", source_type: "ai_generated", source_transcript_segment_id: null, source_media_id: null, timestamp_start: null, timestamp_end: null, ai_model: "fake", prompt_version: "test", confidence: 0.9, flags: {}, review_status: "confirmed", reviewed_by: propertyId, reviewed_at: now }], transcript: [], report: { id: reportId, template_id: "real_estate_v1", status: status === "draft" ? "pending_review" : "confirmed", rendered_html: status === "draft" ? null : "<p>Report</p>", content: { executive_summary: "Bright kitchen.", room_by_room: [{ zone_id: zoneId, zone_type: "kitchen", bullets: [{ text: "Strong natural light.", observation_ids: [observationId] }] }], highlights: [{ text: "Strong natural light.", observation_ids: [observationId] }], concerns: [], follow_ups: [] } } } });
    }
    if (path === `/reports/${reportId}`) return route.fulfill({ json: { id: reportId, template_id: "real_estate_v1", status: "pending_review", rendered_html: null, content: (await route.request().postDataJSON()).content } });
    if (/^\/showings\/[^/]+\/confirm$/.test(path)) {
      expect(route.request().method()).toBe("POST");
      status = "confirmed";
      return route.fulfill({ json: { visit_id: path.split("/")[2], report_id: reportId, visit_status: "confirmed", report_status: "confirmed" } });
    }
    if (/^\/showings\/[^/]+\/send$/.test(path) && route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({ channel: "link_only" });
      sendCount += 1;
      status = "sent_to_client";
      return route.fulfill({ json: { send_id: reportSendId, visit_status: "sent_to_client", channel: "link_only", share_url: shareUrl, to_email: null } });
    }
    if (/^\/showings\/[^/]+\/delivery$/.test(path) && route.request().method() === "GET") {
      return route.fulfill({
        json: {
          share_links: sendCount > 0 ? [{ id: shareLinkId, token: "share-token", url: shareUrl, created_at: now, expires_at: null, revoked: shareLinkRevoked, open_count: 0 }] : [],
          sends: sendCount > 0 ? [{ send_id: reportSendId, channel: "link_only", to_email: null, status: "sent", attempt_count: 0, last_attempt_at: null, sent_at: now, error: null }] : [],
        },
      });
    }
    if (/^\/showings\/[^/]+\/share-links\/[^/]+\/revoke$/.test(path) && route.request().method() === "POST") {
      expect(path).toBe(`/showings/${activeVisitId}/share-links/${shareLinkId}/revoke`);
      shareLinkRevoked = true;
      return route.fulfill({ json: { id: shareLinkId, token: "share-token", url: shareUrl, expires_at: null, revoked_at: "2026-08-04T13:00:00Z" } });
    }
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
  await page.locator("#consent-attestation").check();
  const captureRequest = page.waitForRequest((request) => request.method() === "POST" && new URL(request.url()).pathname.endsWith("/showings"));
  await page.getByRole("button", { name: "Upload and process" }).click();
  expect((await captureRequest).postDataJSON()).toEqual(expect.objectContaining({ consent_ack: true }));
  await expect(page.getByRole("heading", { name: "42 Pipeline Avenue" })).toBeVisible();
  await page.getByTestId("confirm-button").click();
  await expect(page.getByRole("heading", { name: "Send the confirmed report" })).toBeVisible();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  const sendRequest = page.waitForRequest((request) => request.method() === "POST" && /\/showings\/[^/]+\/send$/.test(new URL(request.url()).pathname));
  await page.getByRole("button", { name: "Create private link" }).click();
  expect((await sendRequest).postDataJSON()).toEqual({ channel: "link_only" });
  await expect(page.getByText("Active private link")).toBeVisible();
  await page.getByRole("button", { name: "Copy link" }).first().click();
  await expect(page.getByText("Private report link copied.")).toBeVisible();
  await expect(page.getByText("Share link delivered")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open shared report" })).toHaveAttribute("href", shareUrl);
  await expect(page.getByRole("button", { name: "Revoke" })).toBeVisible();

  let dialogMessage = "";
  page.once("dialog", async (dialog) => {
    dialogMessage = dialog.message();
    await dialog.accept();
  });
  const revokeRequest = page.waitForRequest((request) => request.method() === "POST" && new URL(request.url()).pathname.endsWith(`/share-links/${shareLinkId}/revoke`));
  await page.getByRole("button", { name: "Revoke" }).click();
  expect(dialogMessage).toContain("Revoke this private report link?");
  expect((await revokeRequest).url()).toContain(`/showings/${activeVisitId}/share-links/${shareLinkId}/revoke`);
  await expect(page.getByText("Private report link revoked.")).toBeVisible();
  await expect(page.getByText("Revoked", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Revoke" })).toHaveCount(0);
});

test("captures without a property and attaches one before confirmation", async ({ page, context }) => {
  let status: "draft" | "confirmed" = "draft";
  let propertyAttached = false;
  const now = "2026-08-05T10:00:00Z";
  const property = {
    id: subjectlessPropertyId,
    display_name: "Cedar Lane Home",
    address: "18 Cedar Lane",
    attributes: {},
    created_at: now,
    updated_at: now,
  };
  const audio = {
    id: subjectlessMediaId,
    type: "audio",
    content_type: "audio/mp4",
    timestamp_offset_ms: null,
    status: "completed",
    size_bytes: 10,
    created_at: now,
  };
  const currentProperty = () => propertyAttached ? property : null;
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("https://storage.test/upload/**", (route) =>
    route.fulfill({ status: 200, body: "" }),
  );
  await page.route("**/api/backend/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/backend", "");
    const showingId = path.match(/^\/showings\/([^/]+)$/)?.[1] ?? subjectlessVisitId;
    const summary = {
      id: showingId,
      status,
      processing_status: "ready",
      processing_failed_step: null,
      processing_error: null,
      started_at: now,
      ended_at: now,
      created_at: now,
      updated_at: now,
      property: currentProperty(),
      contact: null,
    };
    if (path === "/properties" && route.request().method() === "GET") {
      return route.fulfill({ json: [property] });
    }
    if (path === "/contacts" && route.request().method() === "GET") {
      return route.fulfill({ json: [] });
    }
    if (path === "/showings" && route.request().method() === "POST") {
      // The browser zone rides along so the report prints the local tour date;
      // its value depends on where the test runs.
      expect(route.request().postDataJSON()).toEqual({
        contact_id: null,
        consent_ack: true,
        capture_timezone: expect.any(String),
      });
      return route.fulfill({ json: summary });
    }
    if (/^\/showings\/[^/]+\/media\/presign$/.test(path)) {
      return route.fulfill({ json: { media_id: subjectlessMediaId, upload_url: "https://storage.test/upload/subjectless", method: "PUT", headers: {}, expires_in: 300, max_size_bytes: 10_000_000 } });
    }
    if (/^\/showings\/[^/]+\/media\/[^/]+\/complete$/.test(path)) {
      return route.fulfill({ json: audio });
    }
    if (/^\/showings\/[^/]+\/finish$/.test(path)) {
      return route.fulfill({ json: {} });
    }
    if (/^\/showings\/[^/]+$/.test(path) && route.request().method() === "GET") {
      return route.fulfill({
        json: {
          ...summary,
          media: [audio],
          zones: [{ id: subjectlessZoneId, zone_type: "kitchen", position: 0, start_transcript_segment_id: null, end_transcript_segment_id: null }],
          observations: [{ id: subjectlessObservationId, zone_id: subjectlessZoneId, category: "light", content: "Strong natural light.", source_type: "ai_generated", source_transcript_segment_id: null, source_media_id: null, timestamp_start: null, timestamp_end: null, ai_model: "fake", prompt_version: "test", confidence: 0.9, flags: {}, review_status: "confirmed", reviewed_by: subjectlessVisitId, reviewed_at: now }],
          transcript: [],
          report: { id: subjectlessReportId, template_id: "real_estate_v1", status: status === "draft" ? "pending_review" : "confirmed", rendered_html: status === "draft" ? null : "<p>Report</p>", content: { executive_summary: "A bright kitchen.", room_by_room: [{ zone_id: subjectlessZoneId, zone_type: "kitchen", bullets: [{ text: "Strong natural light.", observation_ids: [subjectlessObservationId] }] }], highlights: [{ text: "Strong natural light.", observation_ids: [subjectlessObservationId] }], concerns: [], follow_ups: [] } },
        },
      });
    }
    if (/^\/showings\/[^/]+$/.test(path) && route.request().method() === "PATCH") {
      expect(route.request().postDataJSON()).toEqual({ subject_id: subjectlessPropertyId });
      propertyAttached = true;
      return route.fulfill({ json: { ...summary, property: currentProperty() } });
    }
    if (path === `/reports/${subjectlessReportId}` && route.request().method() === "PATCH") {
      const body = await route.request().postDataJSON();
      return route.fulfill({ json: { id: subjectlessReportId, template_id: "real_estate_v1", status: "pending_review", rendered_html: null, content: body.content } });
    }
    if (/^\/showings\/[^/]+\/confirm$/.test(path)) {
      expect(propertyAttached).toBe(true);
      status = "confirmed";
      return route.fulfill({ json: { visit_id: subjectlessVisitId, report_id: subjectlessReportId, visit_status: "confirmed", report_status: "confirmed" } });
    }
    return route.continue();
  });

  await page.goto("/signup");
  await page.getByLabel("Email address").fill("subjectless-agent@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Showing reports" })).toBeVisible();
  await page.getByRole("link", { name: "New showing" }).first().click();
  await page.getByRole("radio", { name: /No property yet/ }).check();
  await expect(page.getByText("This showing will be created without a property or address.")).toBeVisible();
  await expect(page.getByPlaceholder("Start typing an address or property name")).toHaveCount(0);
  await page.locator('input[type="file"]').setInputFiles({ name: "subjectless.m4a", mimeType: "audio/mp4", buffer: Buffer.from("fake-audio") });
  await page.locator("#consent-attestation").check();
  await page.getByRole("button", { name: "Upload and process" }).click();

  await expect(page.getByRole("heading", { name: "Unassigned showing" })).toBeVisible();
  await expect(page.getByText("Attach a property before confirming the report.")).toBeVisible();
  await expect(page.getByTestId("confirm-button")).toBeDisabled();
  await page.getByRole("combobox", { name: "Saved property" }).selectOption(subjectlessPropertyId);
  await page.getByRole("button", { name: "Attach property" }).click();
  await expect(page.getByText("Property attached to this showing.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cedar Lane Home" })).toBeVisible();
  await expect(page.getByTestId("confirm-button")).toBeEnabled();
  await page.getByTestId("confirm-button").click();
  await expect(page.getByRole("heading", { name: "Send the confirmed report" })).toBeVisible();
});
