import { test, expect } from '@playwright/test';

import {
  discoverCatalogScenario,
  expectVisibleCardsToMatchAuthor,
  getAppBaseURL,
  getResultCount,
  getVisibleTitles,
  gotoSearchPage,
  runSearch,
  waitForSearchResponse,
  type CatalogScenario,
} from './helpers';

let appBaseURL = '';
let catalog: CatalogScenario;

test.beforeAll(async ({ request }) => {
  appBaseURL = getAppBaseURL();
  catalog = await discoverCatalogScenario(request, appBaseURL);
});

test('search flow renders result cards with title, author, and snippet data', async ({ page }) => {
  test.skip(
    !catalog.highlightScenario,
    'No indexed query with highlight snippets is available in the current local stack.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.highlightScenario!.query);

  const card = page
    .locator('.book-card')
    .filter({ hasText: catalog.highlightScenario!.result.title })
    .first();

  await expect(card).toBeVisible();
  await expect(card.locator('.book-title')).toContainText(catalog.highlightScenario!.result.title);
  await expect(card.locator('.book-meta')).toContainText(catalog.highlightScenario!.result.author!);
  await expect(card.locator('.book-highlight-snippet').first()).toBeVisible();
});

test('author facet filtering narrows results and chip removal restores them', async ({ page }) => {
  test.skip(
    !catalog.facetScenario,
    'No meaningful author facet is available in the current indexed data set.'
  );

  const scenario = catalog.facetScenario!;

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, scenario.query);
  await expect(page.locator('.facet-group-title', { hasText: 'Author' })).toBeVisible();
  expect(await getResultCount(page)).toBe(scenario.baselineTotal);

  const authorFacet = page
    .locator('.facet-group')
    .filter({ has: page.locator('.facet-group-title', { hasText: 'Author' }) });
  const authorLabel = authorFacet.locator('.facet-label').filter({ hasText: scenario.author }).first();
  await expect(authorLabel).toBeVisible();

  const filteredResponse = waitForSearchResponse(
    page,
    (url) =>
      url.searchParams.get('q') === scenario.query &&
      url.searchParams.get('page') === '1' &&
      url.searchParams.get('fq_author') === scenario.author
  );

  await authorLabel.click();
  expect((await filteredResponse).ok()).toBeTruthy();

  await expect(page.locator('.filter-chip-value')).toHaveText(scenario.author);
  expect(await getResultCount(page)).toBe(scenario.filteredTotal);
  await expectVisibleCardsToMatchAuthor(page, scenario.author);

  const restoredResponse = waitForSearchResponse(
    page,
    (url) =>
      url.searchParams.get('q') === scenario.query &&
      url.searchParams.get('page') === '1' &&
      !url.searchParams.has('fq_author')
  );

  await page.getByRole('button', { name: 'Remove Author filter' }).click();
  expect((await restoredResponse).ok()).toBeTruthy();

  await expect(page.locator('.filter-chip')).toHaveCount(0);
  expect(await getResultCount(page)).toBe(scenario.baselineTotal);
});

test('pdf viewer opens from a search result and loads the document iframe', async ({ page }) => {
  test.skip(
    !catalog.pdfScenario,
    'No indexed result with a document URL is available in the current local stack.'
  );

  const scenario = catalog.pdfScenario!;

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, scenario.query);

  const card = page.locator('.book-card').filter({ hasText: scenario.result.title }).first();
  await expect(card).toBeVisible();

  await card.locator('.open-pdf-btn').click();

  const viewer = page.locator('.pdf-viewer-overlay');
  await expect(viewer).toBeVisible();
  await expect(viewer.locator('.pdf-viewer-title strong')).toContainText(scenario.result.title);
  await expect(viewer.locator('.pdf-viewer-frame')).toBeVisible();
  await expect(viewer.locator('.pdf-viewer-frame')).toHaveAttribute('src', /\/documents\//);

  await page.getByRole('button', { name: 'Close PDF viewer' }).click();
  await expect(viewer).toBeHidden();
});

test('pdf viewer supports page fragment navigation for multi-page PDFs', async ({ page }) => {
  test.skip(
    !catalog.multiPagePdfScenario,
    'No multi-page PDF is available in the current indexed data set.'
  );

  const scenario = catalog.multiPagePdfScenario!;

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, scenario.query);

  const card = page.locator('.book-card').filter({ hasText: scenario.result.title }).first();
  await expect(card).toBeVisible();
  await card.locator('.open-pdf-btn').click();

  const frame = page.locator('.pdf-viewer-frame');
  await expect(frame).toBeVisible();

  // The current UI embeds the browser PDF viewer in an iframe, so navigation is
  // exercised through the standard PDF fragment syntax instead of custom controls.
  await frame.evaluate((element) => {
    const iframe = element as HTMLIFrameElement;
    const currentSrc = iframe.getAttribute('src') || '';
    iframe.setAttribute('src', currentSrc.includes('#') ? currentSrc.replace(/#.*/, '#page=2') : `${currentSrc}#page=2`);
  });

  await expect(frame).toHaveAttribute('src', /#page=2$/);
});

test('search pagination requests and displays the next page of results', async ({ page }) => {
  test.skip(
    !catalog.paginationQuery,
    'The current indexed data set does not have enough results to paginate.'
  );

  await gotoSearchPage(page, appBaseURL);
  await runSearch(page, catalog.paginationQuery!);

  await expect(page.locator('.pagination')).toBeVisible();
  await expect(page.locator('.pagination-info')).toHaveText(/Page 1 of /);

  const firstPageTitles = await getVisibleTitles(page);
  const nextPageResponse = waitForSearchResponse(
    page,
    (url) =>
      url.searchParams.get('q') === catalog.paginationQuery && url.searchParams.get('page') === '2'
  );

  await page.getByRole('button', { name: 'Next page' }).click();
  expect((await nextPageResponse).ok()).toBeTruthy();

  await expect(page.locator('.pagination-info')).toHaveText(/Page 2 of /);
  await expect(page.locator('.pagination-btn[aria-current="page"]')).toHaveText('2');

  const secondPageTitles = await getVisibleTitles(page);
  expect(secondPageTitles).not.toEqual(firstPageTitles);
});
