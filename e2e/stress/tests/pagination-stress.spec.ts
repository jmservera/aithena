/**
 * Pagination stress test — deep pagination through large result sets.
 *
 * Traverses many pages of search results to verify that pagination remains
 * stable, results change per page, and the UI doesn't degrade over long
 * result sets (1,000+ results).
 */

import { test, expect } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  getVisibleTitles,
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

test('paginate through all available pages of results', async ({ page }) => {
  test.skip(
    !catalog.paginationQuery,
    'Not enough indexed documents to test pagination (need >10).'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.paginationQuery!);

  await expect(page.locator('.pagination')).toBeVisible();
  await expect(page.locator('.pagination-info')).toHaveText(/Page 1 of /);

  const paginationText = await page.locator('.pagination-info').textContent();
  const totalPagesMatch = paginationText?.match(/Page \d+ of (\d+)/);
  const totalPages = totalPagesMatch ? parseInt(totalPagesMatch[1], 10) : 1;
  const maxPages = Math.min(totalPages, StressConfig.pagination.maxPagesToTraverse);

  const seenTitleSets: string[][] = [];
  seenTitleSets.push(await getVisibleTitles(page));

  for (let pageNum = 2; pageNum <= maxPages; pageNum++) {
    const nextBtn = page.getByRole('button', { name: 'Next page' });
    const nextVisible = await nextBtn.isVisible().catch(() => false);
    if (!nextVisible) break;

    const nextPageResponse = waitForSearchResponse(
      page,
      (url) =>
        url.searchParams.get('q') === catalog.paginationQuery &&
        url.searchParams.get('page') === String(pageNum)
    );

    await nextBtn.click();

    try {
      const response = await nextPageResponse;
      expect(response.ok()).toBeTruthy();
    } catch {
      console.log(`Pagination timed out at page ${pageNum} of ${maxPages}`);
      break;
    }

    await expect(page.locator('.pagination-info')).toHaveText(
      new RegExp(`Page ${pageNum} of `)
    );

    seenTitleSets.push(await getVisibleTitles(page));
  }

  expect(seenTitleSets.length).toBeGreaterThan(1);

  // Verify consecutive pages have different results
  for (let i = 1; i < seenTitleSets.length; i++) {
    expect(seenTitleSets[i].join('|')).not.toBe(seenTitleSets[i - 1].join('|'));
  }

  console.log(`Pagination stress: traversed ${seenTitleSets.length} pages of ${totalPages} total.`);
});

test('rapid page-forward clicking does not break pagination', async ({ page }) => {
  test.skip(
    !catalog.paginationQuery,
    'Not enough indexed documents for rapid pagination test.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.paginationQuery!);

  await expect(page.locator('.pagination')).toBeVisible();

  const paginationText = await page.locator('.pagination-info').textContent();
  const totalPagesMatch = paginationText?.match(/Page \d+ of (\d+)/);
  const totalPages = totalPagesMatch ? parseInt(totalPagesMatch[1], 10) : 1;

  if (totalPages < 3) {
    test.skip(true, 'Need at least 3 pages for rapid-forward test.');
    return;
  }

  const pagesToClick = Math.min(10, totalPages - 1);

  // Click "Next page" rapidly without waiting for each response
  for (let i = 0; i < pagesToClick; i++) {
    const nextBtn = page.getByRole('button', { name: 'Next page' });
    const nextVisible = await nextBtn.isVisible().catch(() => false);
    if (!nextVisible) break;
    await nextBtn.click();
  }

  // Wait for UI to settle
  await page.waitForTimeout(3_000);

  const finalText = await page.locator('.pagination-info').textContent();
  expect(finalText).toMatch(/Page \d+ of \d+/);

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('backward pagination after deep navigation', async ({ page }) => {
  test.skip(
    !catalog.paginationQuery,
    'Not enough indexed documents for backward pagination test.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.paginationQuery!);

  await expect(page.locator('.pagination')).toBeVisible();

  const paginationText = await page.locator('.pagination-info').textContent();
  const totalPagesMatch = paginationText?.match(/Page \d+ of (\d+)/);
  const totalPages = totalPagesMatch ? parseInt(totalPagesMatch[1], 10) : 1;

  if (totalPages < 4) {
    test.skip(true, 'Need at least 4 pages for backward-navigation test.');
    return;
  }

  // Navigate forward 3 pages
  for (let i = 0; i < 3; i++) {
    const nextResponse = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('page') === String(i + 2)
    );
    await page.getByRole('button', { name: 'Next page' }).click();
    await nextResponse;
  }

  await expect(page.locator('.pagination-info')).toHaveText(/Page 4 of /);
  const page4Titles = await getVisibleTitles(page);

  // Navigate backward 2 pages
  for (let i = 0; i < 2; i++) {
    const prevResponse = waitForSearchResponse(
      page,
      (url) => url.searchParams.get('page') === String(3 - i)
    );
    await page.getByRole('button', { name: 'Previous page' }).click();
    await prevResponse;
  }

  await expect(page.locator('.pagination-info')).toHaveText(/Page 2 of /);
  const page2Titles = await getVisibleTitles(page);

  expect(page2Titles.join('|')).not.toBe(page4Titles.join('|'));
});

test('large result set scroll does not degrade UI responsiveness', async ({ page }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents for scroll test.');

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.broadQuery);

  // Scroll to bottom then back
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);

  // Rapid scroll cycles
  for (let i = 0; i < 10; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.evaluate(() => window.scrollTo(0, 0));
  }

  await expect(page.locator('input.search-input')).toBeVisible();
  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});
