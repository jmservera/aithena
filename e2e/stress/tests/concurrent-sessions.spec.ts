/**
 * Concurrent sessions stress test — multiple browser contexts performing
 * different operations simultaneously.
 *
 * Validates that Aithena handles multiple browser sessions (tabs) working
 * in parallel: searching, navigating, uploading, and viewing status — all
 * without interfering with each other.
 */

import { test, expect, type BrowserContext, type Page } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  getVisibleTitles,
  gotoAppPage,
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

test('multiple browser contexts search simultaneously', async ({ browser }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents for concurrent search test.');

  const contextCount = StressConfig.concurrent.browserContexts;
  const queries = ['history', 'barcelona', 'science', 'art', 'literature'];

  const sessions: { context: BrowserContext; page: Page }[] = [];
  for (let i = 0; i < contextCount; i++) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await gotoAppPage(page, appBaseURL, '/search');
    sessions.push({ context, page });
  }

  try {
    const searchPromises = sessions.map(async ({ page }, index) => {
      const query = queries[index % queries.length];
      await page.locator('input.search-input').fill(query);

      const responsePromise = waitForSearchResponse(
        page,
        (url) => url.searchParams.get('q') === query
      );

      await page.locator('button.search-btn').click();

      try {
        const response = await responsePromise;
        return { index, query, ok: response.ok(), status: response.status() };
      } catch {
        return { index, query, ok: false, status: 0 };
      }
    });

    const results = await Promise.all(searchPromises);
    const successCount = results.filter((r) => r.ok).length;
    expect(successCount / contextCount).toBeGreaterThanOrEqual(0.8);

    console.log(
      `Concurrent search: ${successCount}/${contextCount} succeeded. ` +
        `Results: ${results.map((r) => `${r.query}:${r.status}`).join(', ')}`
    );
  } finally {
    for (const { context } of sessions) {
      await context.close();
    }
  }
});

test('mixed workloads across concurrent sessions', async ({ browser }) => {
  const contextCount = Math.min(4, StressConfig.concurrent.browserContexts);

  const sessions: { context: BrowserContext; page: Page }[] = [];
  for (let i = 0; i < contextCount; i++) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await gotoAppPage(page, appBaseURL, '/search');
    sessions.push({ context, page });
  }

  try {
    const workloads = [
      async (page: Page) => {
        await gotoSearchPage(page, appBaseURL);
        if (catalog.totalDocuments > 0) {
          await runSearch(page, catalog.broadQuery);
          await expect(page.locator('.book-card').first()).toBeVisible({ timeout: 15_000 });
        }
      },
      async (page: Page) => {
        const tabs = ['/search', '/status', '/stats', '/library'] as const;
        for (const tab of tabs) {
          await page.locator(`a.tab-nav-link[href="${tab}"]`).click();
          await expect(page).toHaveURL(new RegExp(`${tab}$`));
        }
      },
      async (page: Page) => {
        await gotoAppPage(page, appBaseURL, '/status');
        await expect(page.locator('.status-title')).toContainText('System Status');
        await page.reload({ waitUntil: 'domcontentloaded' });
        await expect(page.locator('.status-title')).toContainText('System Status');
      },
      async (page: Page) => {
        await gotoAppPage(page, appBaseURL, '/stats');
        await expect(page.locator('.stats-page-title')).toContainText('Collection Stats');
      },
    ];

    const results = await Promise.allSettled(
      sessions.map(({ page }, index) => workloads[index % workloads.length](page))
    );

    const fulfilled = results.filter((r) => r.status === 'fulfilled').length;
    expect(fulfilled).toBe(contextCount);
  } finally {
    for (const { context } of sessions) {
      await context.close();
    }
  }
});

test('concurrent sessions do not corrupt shared search state', async ({ browser }) => {
  test.skip(catalog.totalDocuments === 0, 'No indexed documents for state isolation test.');

  const context1 = await browser.newContext();
  const context2 = await browser.newContext();
  const page1 = await context1.newPage();
  const page2 = await context2.newPage();

  try {
    await gotoAppPage(page1, appBaseURL, '/search');
    await gotoAppPage(page2, appBaseURL, '/search');

    const query1 = catalog.broadQuery;
    await page1.locator('input.search-input').fill(query1);
    const resp1Promise = waitForSearchResponse(
      page1,
      (url) => url.searchParams.get('q') === query1
    );
    await page1.locator('button.search-btn').click();
    await resp1Promise;

    const query2 = catalog.highlightScenario?.query || 'test';
    await page2.locator('input.search-input').fill(query2);
    const resp2Promise = waitForSearchResponse(
      page2,
      (url) => url.searchParams.get('q') === query2
    );
    await page2.locator('button.search-btn').click();
    await resp2Promise;

    await expect(page1.locator('input.search-input')).toHaveValue(query1);
    await expect(page2.locator('input.search-input')).toHaveValue(query2);

    if (query1 !== query2) {
      const titles1 = await getVisibleTitles(page1);
      const titles2 = await getVisibleTitles(page2);
      console.log(
        `Session isolation: Context 1 (${query1}): ${titles1.length} results, ` +
          `Context 2 (${query2}): ${titles2.length} results`
      );
    }
  } finally {
    await context1.close();
    await context2.close();
  }
});

test('long-running session stability over many repeated actions', async ({ page }) => {
  await gotoSearchPage(page, appBaseURL);

  const totalActions = StressConfig.concurrent.actionsPerContext * 3;
  const queries = ['*', 'history', 'barcelona', 'art', 'science'];
  const tabs = ['/search', '/status', '/stats', '/library'] as const;
  let completedActions = 0;

  for (let i = 0; i < totalActions; i++) {
    const action = i % 3;

    try {
      switch (action) {
        case 0: {
          const query = queries[i % queries.length];
          await page.locator('a.tab-nav-link[href="/search"]').click();
          await expect(page).toHaveURL(/\/search$/);

          if (catalog.totalDocuments > 0) {
            await page.locator('input.search-input').fill(query);
            const responsePromise = waitForSearchResponse(
              page,
              (url) => url.searchParams.get('q') === query
            );
            await page.locator('button.search-btn').click();
            await responsePromise;
          }
          break;
        }
        case 1: {
          const tab = tabs[i % tabs.length];
          await page.locator(`a.tab-nav-link[href="${tab}"]`).click();
          await expect(page).toHaveURL(new RegExp(`${tab}$`));
          break;
        }
        case 2: {
          await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
          await page.evaluate(() => window.scrollTo(0, 0));
          break;
        }
      }

      completedActions++;
    } catch {
      console.log(`Long-running session: action ${i} (type ${action}) failed — continuing.`);
    }
  }

  expect(completedActions / totalActions).toBeGreaterThanOrEqual(0.9);
  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
  console.log(`Long-running session: ${completedActions}/${totalActions} actions completed.`);
});

test('memory leak detection via heap snapshot comparison', async ({ page }) => {
  const cdpSession = await page.context().newCDPSession(page).catch(() => null);
  if (!cdpSession) {
    test.skip(true, 'CDP not available — heap profiling requires Chromium.');
    return;
  }

  await gotoSearchPage(page, appBaseURL);

  await cdpSession.send('HeapProfiler.collectGarbage');
  const initialMetrics = await page.evaluate(() => {
    if ('memory' in performance) {
      return (performance as { memory: { usedJSHeapSize: number } }).memory.usedJSHeapSize;
    }
    return null;
  });

  if (initialMetrics === null) {
    test.skip(true, 'performance.memory not available — heap comparison not possible.');
    await cdpSession.detach();
    return;
  }

  // Perform many search + navigation cycles
  const queries = ['*', 'history', 'barcelona', 'science', 'art'];
  for (let cycle = 0; cycle < 5; cycle++) {
    for (const query of queries) {
      if (catalog.totalDocuments > 0) {
        await page.locator('input.search-input').fill(query);
        const responsePromise = waitForSearchResponse(
          page,
          (url) => url.searchParams.get('q') === query
        ).catch(() => null);
        await page.locator('button.search-btn').click();
        await responsePromise;
      }
    }

    for (const tab of ['/search', '/status', '/stats']) {
      await page.locator(`a.tab-nav-link[href="${tab}"]`).click();
      await page.waitForTimeout(200);
    }
  }

  // Force GC and measure final heap
  await cdpSession.send('HeapProfiler.collectGarbage');
  await page.waitForTimeout(1_000);

  const finalMetrics = await page.evaluate(() => {
    if ('memory' in performance) {
      return (performance as { memory: { usedJSHeapSize: number } }).memory.usedJSHeapSize;
    }
    return null;
  });

  await cdpSession.detach();

  if (finalMetrics !== null) {
    const growthMB = (finalMetrics - initialMetrics) / (1024 * 1024);
    const growthPct = ((finalMetrics - initialMetrics) / initialMetrics) * 100;

    console.log(
      `Heap: initial=${(initialMetrics / 1024 / 1024).toFixed(1)}MB, ` +
        `final=${(finalMetrics / 1024 / 1024).toFixed(1)}MB, ` +
        `growth=${growthMB.toFixed(1)}MB (${growthPct.toFixed(1)}%)`
    );

    // Flag gross memory leaks only — 50MB threshold is generous
    expect(growthMB).toBeLessThan(50);
  }
});
