import { expect, test } from '@playwright/test';
import { z } from 'zod';
import { showingSchema, observationSchema, reportSchema } from '../lib/api';
const detailSchema = showingSchema.extend({ observations: z.array(observationSchema), report: reportSchema });

test('real API persists capture, evidence, edits after refresh, confirmation and private delivery', async ({ page, context }) => {
  const apiRequest = async (path: string, method = 'GET', data?: unknown) => page.evaluate(async ({ path, method, data }) => {
    const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) });
    return { status: response.status, ok: response.ok, body: await response.json() };
  }, { path, method, data });
  // Only storage bytes are mocked at the browser boundary; the Python harness
  // runs the real pipeline with fake AI providers and real PostgreSQL state.
  await page.route('https://storage.test/upload/**', route => route.fulfill({ status: 200, body: '' }));
  await page.goto('/signup');
  await page.getByLabel('Email address').fill(`integrated-${Date.now()}@example.com`);
  await page.getByLabel('Password').fill('correct-horse-battery-staple');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Showing reports' })).toBeVisible();
  await page.getByRole('link', { name: 'New showing' }).first().click();
  await page.getByPlaceholder('Start typing an address or property name').fill('12 Integration Avenue');
  await page.locator('input[type="file"]').setInputFiles({ name: 'tour.m4a', mimeType: 'audio/mp4', buffer: Buffer.from('fake audio provider fixture') });
  await page.locator('#consent-attestation').check();
  await page.getByRole('button', { name: 'Upload and process' }).click();
  await expect(page).toHaveURL(/\/showings\/[a-f0-9-]+$/);
  const visitId = page.url().split('/').at(-1)!;
  await expect.poll(async () => showingSchema.parse((await apiRequest(`/api/backend/showings/${visitId}`)).body).processing_status).toBe('ready');
  const detail = detailSchema.parse((await apiRequest(`/api/backend/showings/${visitId}`)).body);
  expect(detail.observations.length).toBeGreaterThan(0);
  expect(detail.observations[0].source_transcript_segment_id).toBeTruthy();
  expect(detail.observations[0].source_media_id).toBeTruthy();
  expect((await apiRequest(`/api/backend/showings/${visitId}/send`, 'POST', { channel: 'link_only' })).ok).toBe(false);

  // Expire only access credentials. Navigation must restore via the real proxy.
  await context.clearCookies({ name: 'homean_access' });
  await page.reload();
  await expect(page.getByRole('heading', { name: '12 Integration Avenue' })).toBeVisible();
  await context.clearCookies({ name: 'homean_access' });
  const edited = { ...detail.report.content, executive_summary: 'Agent-reviewed integration summary.' };
  const saved = await apiRequest(`/api/backend/reports/${detail.report.id}`, 'PATCH', { content: edited });
  expect(saved.status).toBe(200);
  expect(reportSchema.parse(saved.body).content.executive_summary).toBe(edited.executive_summary);
  for (const observation of detail.observations) {
    const review = await apiRequest(`/api/backend/observations/${observation.id}/confirm`, 'POST');
    expect(review.ok).toBe(true);
  }
  await page.reload();
  await page.getByTestId('confirm-button').click();
  await expect(page.getByRole('heading', { name: 'Send the confirmed report' })).toBeVisible();
  await page.getByRole('button', { name: 'Create private link' }).click();
  const shared = page.getByRole('link', { name: 'Open shared report' }).first();
  await expect(shared).toBeVisible();
  const url = (await shared.getAttribute('href'))!;
  const publicReport = await context.request.get(url);
  expect(publicReport.ok()).toBe(true);
  expect(await publicReport.text()).toContain('Agent-reviewed integration summary.');
  const persisted = detailSchema.parse((await apiRequest(`/api/backend/showings/${visitId}`)).body);
  expect(persisted.status).toBe('sent_to_client');
  expect(persisted.report.content.executive_summary).toBe(edited.executive_summary);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Revoke', exact: true }).click();
  await expect(page.getByText('Private report link revoked.')).toBeVisible();
  expect((await context.request.get(url)).status()).toBe(404);
});
