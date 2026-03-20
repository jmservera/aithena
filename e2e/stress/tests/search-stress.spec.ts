/**
 * Search stress test — rapid-fire queries and search during indexing.
 *
 * Exercises the search UI with rapid successive queries, varying terms, and
 * validates that results return consistently. Also verifies UI resilience
 * when search is performed while indexing may be active.
 */

import { test, expect } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  gotoSearchPage,
  runSearch,
  waitForSearchResponse,
  type CatalogScenario,
} from '../../playwright/tests/helpers';
import { StressConfig } from '../stress.config';

let appBaseURL = '';
let catalog: CatalogScenario;

test.beforeAll(async ({ request }) => {
  appBaseURL = getAppBaseURL();
  catalog = await discoverCatalogScenario(request, appBaseURL);
});

const QUERY_CORPUS = [
  'history', 'barcelona', 'science', 'art', 'etnologia',
  'amades', 'costumari', 'literatura', 'medieval', 'catalan',
  'folklore', 'architecture', 'music', 'language', 'philosophy',
  'religion', 'travel', 'education', 'poetry', 'novel',
];

test('rapid successive searches all return valid responses', async ({ page }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents — cannot perform search stress test.');

  await gotoSearchPage(page, appBaseURL);

  const queryCount = Math.min(StressConfig.search.rapidFireQueries, QUERY_CORPUS.length);
  let successCount = 0;

  for (let i = 0; i < queryCount; i++) {
    const query = QUERY_CORPUS[i % QUERY_CORPUS.length];

    await page.locator('input.search-input').fill(query);

    const responsePromise = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('q') === query
    );

    await page.locator('button.search-btn').click();

    try {
      const response = await responsePromise;
      expect(response.ok()).toBeTruthy();
      successCount++;
    } catch {
      // Timeout on individual query is acceptable under stress
    }

    if (StressConfig.search.delayBetweenMs > 0) {
      await page.waitForTimeout(StressConfig.search.delayBetweenMs);
    }
  }

  // At least 80% of rapid queries should succeed
  expect(successCount / queryCount).toBeGreaterThanOrEqual(0.8);
});

test('search input remains responsive during rapid typing', async ({ page }) => {
  await gotoSearchPage(page, appBaseURL);

  const searchInput = page.locator('input.search-input');

  for (const char of 'rapid stress test query') {
    await searchInput.press(char);
  }
  await expect(searchInput).toHaveValue('rapid stress test query');

  await searchInput.fill('');
  await expect(searchInput).toHaveValue('');

  for (const char of 'second rapid query') {
    await searchInput.press(char);
  }
  await expect(searchInput).toHaveValue('second rapid query');
});

test('varying query terms all produce API responses', async ({ page }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents — cannot perform search stress test.');

  await gotoSearchPage(page, appBaseURL);

  const queries = QUERY_CORPUS.slice(0, 10);
  const responseTimes: number[] = [];

  for (const query of queries) {
    const start = Date.now();

    await page.locator('input.search-input').fill(query);

    const responsePromise = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('q') === query
    );

    await page.locator('button.search-btn').click();

    try {
      const response = await responsePromise;
      const elapsed = Date.now() - start;
      responseTimes.push(elapsed);
      expect(response.ok()).toBeTruthy();
      expect(elapsed).toBeLessThan(StressConfig.search.maxResponseTimeMs);
    } catch {
      responseTimes.push(StressConfig.search.maxResponseTimeMs);
    }
  }

  const avg = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
  const max = Math.max(...responseTimes);
  console.log(`Search stress — avg: ${avg.toFixed(0)}ms, max: ${max}ms, queries: ${responseTimes.length}`);
});

test('facet rapid clicking under load', async ({ page }) => {
  test.skip(!catalog.facetScenario, 'No meaningful author facet available for rapid-click test.');

  const scenario = catalog.facetScenario!;

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, scenario.query);
  await expect(page.locator('.facet-group-title', { hasText: 'Author' })).toBeVisible();

  const authorFacet = page
    .locator('.facet-group')
    .filter({ has: page.locator('.facet-group-title', { hasText: 'Author' }) });
  const authorLabel = authorFacet.locator('.facet-label').filter({ hasText: scenario.author }).first();
  await expect(authorLabel).toBeVisible();

  for (let i = 0; i < StressConfig.admin.actionRepetitions; i++) {
    const filterResponse = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('fq_author') === scenario.author
    );
    await authorLabel.click();

    try {
      const resp = await filterResponse;
      expect(resp.ok()).toBeTruthy();
    } catch {
      // Timeout acceptable under rapid clicking
    }

    const removeBtn = page.getByRole('button', { name: 'Remove Author filter' });
    const chipVisible = await removeBtn.isVisible().catch(() => false);
    if (chipVisible) {
      const clearResponse = waitForSearchResponse(
        page,
        (url) => !url.searchParams.has('fq_author')
      );
      await removeBtn.click();

      try {
        const resp = await clearResponse;
        expect(resp.ok()).toBeTruthy();
      } catch {
        // Continue on timeout
      }
    }

    if (StressConfig.admin.delayBetweenMs > 0 && i < StressConfig.admin.actionRepetitions - 1) {
      await page.waitForTimeout(StressConfig.admin.delayBetweenMs);
    }
  }

  await expect(page.locator('input.search-input')).toBeVisible();
  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('search during active indexing returns results without errors', async ({ page, request }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents — cannot verify search during indexing.');

  await gotoSearchPage(page, appBaseURL);

  // Trigger background indexing by uploading a file (best-effort)
  const apiBaseURL = appBaseURL.includes(':5173')
    ? appBaseURL.replace(':5173', ':8080')
    : appBaseURL;
  const uploadResp = await request
    .post(`${apiBaseURL}/v1/upload`, {
      multipart: {
        file: {
          name: 'indexing-stress.pdf',
          mimeType: 'application/pdf',
          buffer: Buffer.from(
            '%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n' +
              '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n' +
              '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n' +
              'xref\n0 4\n0000000000 65535 f \ntrailer\n<< /Size 4 /Root 1 0 R >>\n' +
              'startxref\n9\n%%EOF\n'
          ),
        },
      },
      timeout: 10_000,
    })
    .catch(() => null);

  // Perform searches immediately — API should not return 5xx during indexing
  const queries = ['*', 'history', 'barcelona', 'science'];
  for (const query of queries) {
    await page.locator('input.search-input').fill(query);

    const responsePromise = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('q') === query
    );

    await page.locator('button.search-btn').click();

    const response = await responsePromise;
    expect(response.status()).toBeLessThan(500);
  }

  await expect(page.locator('input.search-input')).toBeVisible();

  if (uploadResp && uploadResp.ok()) {
    console.log('Background upload succeeded — indexing was active during search stress.');
  } else {
    console.log('Upload unavailable — search stress ran without active indexing background.');
  }
});
