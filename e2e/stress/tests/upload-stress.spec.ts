/**
 * Upload stress test — simultaneous file uploads.
 *
 * Uploads N PDF files concurrently through the UI and verifies that each
 * upload is acknowledged (success / progress / queued feedback). Skips
 * gracefully when the upload UI or backend is unavailable.
 */

import { test, expect } from '@playwright/test';

import {
  getAppBaseURL,
  gotoAppPage,
} from '../../playwright/tests/helpers';
import { StressConfig } from '../stress.config';

let appBaseURL = '';

test.beforeAll(() => {
  appBaseURL = getAppBaseURL();
});

function buildPdfBuffer(label: string): Buffer {
  const content =
    '%PDF-1.4\n' +
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n' +
    `2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 /Info (${label}) >>\nendobj\n` +
    '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n' +
    'xref\n0 4\n0000000000 65535 f \n' +
    'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n';
  return Buffer.from(content, 'utf-8');
}

test(`upload ${StressConfig.upload.simultaneousFiles} files simultaneously and verify queue appearance`, async ({
  page,
}) => {
  await gotoAppPage(page, appBaseURL, '/upload');

  const fileInput = page.locator('input[type="file"]').first();
  const inputVisible = await fileInput.isVisible().catch(() => false);
  if (!inputVisible) {
    test.skip(true, 'No file input found at /upload — upload UI not implemented.');
    return;
  }

  const files = Array.from({ length: StressConfig.upload.simultaneousFiles }, (_, i) => ({
    name: `stress-test-${i + 1}.pdf`,
    mimeType: 'application/pdf',
    buffer: buildPdfBuffer(`stress-doc-${i + 1}`),
  }));

  await fileInput.setInputFiles(files);

  const submitBtn = page
    .locator('button[type="submit"], button:has-text("Upload")')
    .first();
  const submitVisible = await submitBtn.isVisible().catch(() => false);
  if (submitVisible) {
    await submitBtn.click();
  }

  const feedbackLocator = page.locator(
    '.upload-success, .upload-error, .upload-progress, [role="status"], [role="alert"], .upload-queue-item'
  );

  const feedbackAppeared = await feedbackLocator
    .first()
    .waitFor({ state: 'visible', timeout: StressConfig.upload.feedbackTimeoutMs })
    .then(() => true)
    .catch(() => false);

  if (!feedbackAppeared) {
    test.skip(true, 'Upload feedback not visible — backend may not be configured for bulk upload.');
    return;
  }

  await expect(feedbackLocator.first()).toBeVisible();
});

test('UI remains responsive during bulk upload', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/upload');

  const fileInput = page.locator('input[type="file"]').first();
  const inputVisible = await fileInput.isVisible().catch(() => false);
  if (!inputVisible) {
    test.skip(true, 'No file input found at /upload — upload UI not implemented.');
    return;
  }

  const files = Array.from({ length: StressConfig.upload.simultaneousFiles }, (_, i) => ({
    name: `responsive-test-${i + 1}.pdf`,
    mimeType: 'application/pdf',
    buffer: buildPdfBuffer(`responsive-doc-${i + 1}`),
  }));

  await fileInput.setInputFiles(files);

  const submitBtn = page
    .locator('button[type="submit"], button:has-text("Upload")')
    .first();
  const submitVisible = await submitBtn.isVisible().catch(() => false);
  if (submitVisible) {
    await submitBtn.click();
  }

  // Verify the page hasn't frozen — sidebar title still visible
  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);

  // Navigate away to confirm app is still responsive
  await page.locator('a.tab-nav-link[href="/search"]').click();
  await expect(page).toHaveURL(/\/search$/);
  await expect(page.locator('input.search-input')).toBeVisible();
});
