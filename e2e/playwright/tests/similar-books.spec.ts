/**
 * Playwright E2E tests for the similar-books feature.
 *
 * The SimilarBooks panel renders below the search results whenever a book is
 * selected via its "Open PDF" button.  The actual UI flow is:
 *
 *   1. Search for a query that returns results with a `document_url`.
 *   2. Click the "📄 Open PDF" button (.open-pdf-btn) on a result card.
 *   3. The SimilarBooks panel (.similar-books-panel) appears below the results.
 *   4. The PDF viewer overlay (.pdf-viewer-overlay) also opens.
 *   5. Closing the PDF viewer (button[aria-label="Close PDF viewer"]) hides both.
 *
 * All tests skip gracefully when no indexed data with a document_url is available,
 * following the same pattern as search.spec.ts.
 *
 * Coverage matrix
 * ~~~~~~~~~~~~~~~
 *
 * | Scenario                                             | Gated | Note                              |
 * |------------------------------------------------------|-------|-----------------------------------|
 * | SimilarBooks panel appears after Open PDF click      | Yes   | requires result with document_url |
 * | SimilarBooks panel shows book cards                  | Yes   | requires embeddings + data        |
 * | Source book title absent from similar-books results  | Yes   | requires embeddings + data        |
 * | Closing PDF viewer hides SimilarBooks panel          | Yes   | requires result with document_url |
 */

import { test, expect, type Page } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  gotoSearchPage,
  runSearch,
  type CatalogScenario,
} from './helpers';

let appBaseURL = '';
let catalog: CatalogScenario;

/** HTTP status codes that indicate the embeddings service is unavailable. */
const EMBEDDINGS_UNAVAILABLE_CODES = new Set([422, 502, 503]);

test.beforeAll(async ({ request }) => {
  appBaseURL = getAppBaseURL();
  catalog = await discoverCatalogScenario(request, appBaseURL);
});

// ---------------------------------------------------------------------------
// Helper: open a PDF from a search result and wait for the similar-books API
// ---------------------------------------------------------------------------

/**
 * Search for `query`, click the "Open PDF" button on the card matching
 * `resultTitle`, and return the resolved similar-books API response.
 */
async function openPdfAndWaitForSimilarBooks(
  page: Page,
  query: string,
  resultTitle: string
) {
  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, query);

  const card = page.locator('.book-card').filter({ hasText: resultTitle }).first();
  await expect(card).toBeVisible();

  const similarPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/books/') &&
      response.url().includes('/similar') &&
      response.request().method() === 'GET',
    { timeout: 20_000 }
  );

  await card.locator('.open-pdf-btn').click();
  return similarPromise;
}

// ---------------------------------------------------------------------------
// SimilarBooks panel appearance
// ---------------------------------------------------------------------------

test('SimilarBooks panel appears below search results after Open PDF is clicked', async ({ page }) => {
  test.skip(
    !catalog.pdfScenario,
    'No indexed result with a document_url is available — similar-books panel cannot be tested.'
  );

  const scenario = catalog.pdfScenario!;
  const similarResponse = await openPdfAndWaitForSimilarBooks(
    page,
    scenario.query,
    scenario.result.title
  );

  if (EMBEDDINGS_UNAVAILABLE_CODES.has(similarResponse.status())) {
    test.skip(
      true,
      `Similar-books API returned ${similarResponse.status()} — embeddings service may not be running.`
    );
    return;
  }

  // The SimilarBooks component renders as <section class="similar-books-panel">
  const panel = page.locator('.similar-books-panel');
  await expect(panel).toBeVisible({ timeout: 10_000 });
  await expect(panel.locator('#similar-books-title')).toHaveText('Similar Books');
});

// ---------------------------------------------------------------------------
// SimilarBooks panel content
// ---------------------------------------------------------------------------

test('SimilarBooks panel shows book cards when embeddings are available', async ({ page }) => {
  test.skip(
    !catalog.pdfScenario,
    'No indexed result with a document_url is available — similar-books content cannot be tested.'
  );

  const scenario = catalog.pdfScenario!;
  const similarResponse = await openPdfAndWaitForSimilarBooks(
    page,
    scenario.query,
    scenario.result.title
  );

  if (!similarResponse.ok()) {
    test.skip(
      true,
      `Similar-books API returned ${similarResponse.status()} — embeddings service may not be running.`
    );
    return;
  }

  const payload = await similarResponse.json() as { results?: unknown[] };
  if (!payload.results || payload.results.length === 0) {
    test.skip(true, 'Similar-books API returned an empty list — no related books to verify in the UI.');
    return;
  }

  const panel = page.locator('.similar-books-panel');
  await expect(panel).toBeVisible({ timeout: 10_000 });

  // Each similar book renders as a button.similar-book-card with a title and author
  const cards = panel.locator('.similar-book-card');
  await expect(cards.first()).toBeVisible();

  const firstTitle = panel.locator('.similar-book-card__title').first();
  await expect(firstTitle).toBeVisible();
  await expect(firstTitle).not.toBeEmpty();
});

// ---------------------------------------------------------------------------
// Source book exclusion
// ---------------------------------------------------------------------------

test('source book title is not present in the similar-books panel', async ({ page }) => {
  test.skip(
    !catalog.pdfScenario,
    'No indexed result with a document_url is available — exclusion check cannot be performed.'
  );

  const scenario = catalog.pdfScenario!;
  const sourceTitle = scenario.result.title;

  const similarResponse = await openPdfAndWaitForSimilarBooks(
    page,
    scenario.query,
    sourceTitle
  );

  if (!similarResponse.ok()) {
    test.skip(
      true,
      `Similar-books API returned ${similarResponse.status()} — exclusion check skipped.`
    );
    return;
  }

  const panel = page.locator('.similar-books-panel');
  await expect(panel).toBeVisible({ timeout: 10_000 });

  // Collect all rendered similar-book titles from the panel
  const similarTitles = await panel.locator('.similar-book-card__title').allTextContents();
  const normalizedTitles = similarTitles.map((t) => t.trim());

  expect(normalizedTitles).not.toContain(sourceTitle);
});

// ---------------------------------------------------------------------------
// Dismiss behavior: closing PDF viewer hides SimilarBooks panel
// ---------------------------------------------------------------------------

test('closing the PDF viewer also hides the similar-books panel', async ({ page }) => {
  test.skip(
    !catalog.pdfScenario,
    'No indexed result with a document_url is available — dismiss behavior cannot be tested.'
  );

  const scenario = catalog.pdfScenario!;
  await openPdfAndWaitForSimilarBooks(page, scenario.query, scenario.result.title);

  // Wait for the panel to appear (embeddings may or may not be available;
  // we only need the panel element to exist before testing dismiss)
  const panel = page.locator('.similar-books-panel');
  await expect(panel).toBeVisible({ timeout: 10_000 });

  // The PDF viewer close button is always present and sets selectedBook = null,
  // which removes both the PDF viewer overlay and the SimilarBooks panel.
  await page.getByRole('button', { name: 'Close PDF viewer' }).click();

  await expect(panel).toBeHidden({ timeout: 10_000 });
  await expect(page.locator('.pdf-viewer-overlay')).toBeHidden({ timeout: 10_000 });
});
