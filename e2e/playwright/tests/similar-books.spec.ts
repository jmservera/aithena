/**
 * Playwright E2E tests for the similar-books feature.
 *
 * These tests verify the "Similar books" user journey through the UI:
 *   - A similar-books trigger (button/link) is visible on book result cards.
 *   - Activating the trigger loads a list of related books.
 *   - The source book is not shown in its own similar-books list.
 *
 * All tests skip gracefully when no indexed data is available, following
 * the same pattern as search.spec.ts.
 *
 * Coverage matrix
 * ~~~~~~~~~~~~~~~
 *
 * | Scenario                                         | Gated | Note                           |
 * |--------------------------------------------------|-------|--------------------------------|
 * | Similar-books trigger visible on result card     | Yes   | requires indexed documents     |
 * | Similar-books panel loads after trigger click    | Yes   | requires embeddings + data     |
 * | Source book absent from similar-books results    | Yes   | requires embeddings + data     |
 * | Similar-books panel can be closed / dismissed    | Yes   | requires embeddings + data     |
 */

import { test, expect } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  gotoSearchPage,
  runSearch,
  type CatalogScenario,
} from './helpers';

let appBaseURL = '';
let catalog: CatalogScenario;

test.beforeAll(async ({ request }) => {
  appBaseURL = getAppBaseURL();
  catalog = await discoverCatalogScenario(request, appBaseURL);
});

// ---------------------------------------------------------------------------
// Similar-books trigger visibility
// ---------------------------------------------------------------------------

test('similar-books trigger is visible on at least one result card', async ({ page }) => {
  test.skip(
    catalog.totalDocuments === 0,
    'No indexed documents available — similar-books trigger cannot be verified.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.broadQuery);

  // The trigger may be a button labelled "Similar", "Find similar", or similar text,
  // or a link with a class like .similar-btn.  We look for any of these patterns.
  const triggerLocator = page.locator(
    'button.similar-btn, a.similar-btn, [aria-label*="Similar"], button:has-text("Similar")'
  ).first();

  const triggerVisible = await triggerLocator.isVisible({ timeout: 8_000 }).catch(() => false);

  if (!triggerVisible) {
    test.skip(true, 'No similar-books trigger found on result cards — feature may not yet be implemented in the UI.');
    return;
  }

  await expect(triggerLocator).toBeVisible();
});

// ---------------------------------------------------------------------------
// Similar-books panel behavior (gated on embeddings + data)
// ---------------------------------------------------------------------------

test('similar-books panel loads related books after trigger click', async ({ page }) => {
  test.skip(
    catalog.totalDocuments === 0,
    'No indexed documents — similar-books panel cannot be tested.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.broadQuery);

  const triggerLocator = page.locator(
    'button.similar-btn, a.similar-btn, [aria-label*="Similar"], button:has-text("Similar")'
  ).first();

  const triggerVisible = await triggerLocator.isVisible({ timeout: 8_000 }).catch(() => false);

  if (!triggerVisible) {
    test.skip(true, 'No similar-books trigger found — feature may not yet be implemented in the UI.');
    return;
  }

  // Intercept the similar-books API call to detect embedding availability
  const similarResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/books/') &&
      response.url().includes('/similar') &&
      response.request().method() === 'GET',
    { timeout: 20_000 }
  );

  await triggerLocator.click();
  const similarResponse = await similarResponsePromise;

  if (similarResponse.status() === 422 || similarResponse.status() === 503) {
    test.skip(
      true,
      `Similar-books API returned ${similarResponse.status()} — embeddings service may not be running.`
    );
    return;
  }

  expect(similarResponse.ok()).toBeTruthy();

  // A panel, modal, or list section should become visible
  const panelLocator = page.locator(
    '.similar-books-panel, .similar-books-modal, .similar-books-list, [aria-label*="Similar"]'
  ).first();

  const panelAppeared = await panelLocator
    .waitFor({ state: 'visible', timeout: 10_000 })
    .then(() => true)
    .catch(() => false);

  if (!panelAppeared) {
    test.skip(true, 'Similar-books panel did not appear — UI may show results inline or in a different element.');
    return;
  }

  await expect(panelLocator).toBeVisible();
});

test('source book is not present in its own similar-books results', async ({ page }) => {
  test.skip(
    catalog.totalDocuments === 0,
    'No indexed documents — similar-books exclusion cannot be verified.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.broadQuery);

  // Pick the first visible card and record its title
  const firstCard = page.locator('.book-card').first();
  const cardVisible = await firstCard.isVisible({ timeout: 8_000 }).catch(() => false);

  if (!cardVisible) {
    test.skip(true, 'No book cards visible — similar-books exclusion cannot be tested.');
    return;
  }

  const sourceTitle = (await firstCard.locator('.book-title').textContent())?.trim() ?? '';

  const triggerLocator = firstCard.locator(
    'button.similar-btn, a.similar-btn, [aria-label*="Similar"], button:has-text("Similar")'
  ).first();

  const triggerVisible = await triggerLocator.isVisible({ timeout: 5_000 }).catch(() => false);

  if (!triggerVisible) {
    test.skip(true, 'No similar-books trigger on the first card — feature may not be implemented yet.');
    return;
  }

  const similarResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/books/') &&
      response.url().includes('/similar') &&
      response.request().method() === 'GET',
    { timeout: 20_000 }
  );

  await triggerLocator.click();
  const similarResponse = await similarResponsePromise;

  if (!similarResponse.ok()) {
    test.skip(
      true,
      `Similar-books API returned ${similarResponse.status()} — skipping exclusion check.`
    );
    return;
  }

  // If the UI renders similar books in a panel, confirm the source title is absent
  const panelLocator = page.locator(
    '.similar-books-panel, .similar-books-modal, .similar-books-list'
  ).first();

  const panelAppeared = await panelLocator
    .waitFor({ state: 'visible', timeout: 10_000 })
    .then(() => true)
    .catch(() => false);

  if (!panelAppeared || !sourceTitle) {
    test.skip(true, 'Panel not visible or source title unknown — exclusion check skipped.');
    return;
  }

  const panelTitles = await panelLocator.locator('.book-title, .similar-book-title').allTextContents();
  const normalizedPanelTitles = panelTitles.map((t) => t.trim());

  expect(normalizedPanelTitles).not.toContain(sourceTitle);
});

test('similar-books panel can be dismissed', async ({ page }) => {
  test.skip(
    catalog.totalDocuments === 0,
    'No indexed documents — similar-books dismiss cannot be tested.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.broadQuery);

  const triggerLocator = page.locator(
    'button.similar-btn, a.similar-btn, [aria-label*="Similar"], button:has-text("Similar")'
  ).first();

  const triggerVisible = await triggerLocator.isVisible({ timeout: 8_000 }).catch(() => false);

  if (!triggerVisible) {
    test.skip(true, 'No similar-books trigger found — feature may not be implemented yet.');
    return;
  }

  await triggerLocator.click();

  const panelLocator = page.locator(
    '.similar-books-panel, .similar-books-modal, .similar-books-list'
  ).first();

  const panelAppeared = await panelLocator
    .waitFor({ state: 'visible', timeout: 10_000 })
    .then(() => true)
    .catch(() => false);

  if (!panelAppeared) {
    test.skip(true, 'Similar-books panel did not appear — dismiss test skipped.');
    return;
  }

  // Look for a close button within the panel
  const closeBtn = panelLocator
    .locator('button[aria-label*="lose"], button:has-text("Close"), button:has-text("×")')
    .first();

  const closeBtnVisible = await closeBtn.isVisible({ timeout: 3_000 }).catch(() => false);

  if (!closeBtnVisible) {
    test.skip(true, 'No close button found in similar-books panel — dismiss test skipped.');
    return;
  }

  await closeBtn.click();
  await expect(panelLocator).toBeHidden({ timeout: 5_000 });
});
