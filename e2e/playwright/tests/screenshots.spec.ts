import { expect, test, type Browser, type Page, type TestInfo } from '@playwright/test';

import {
  discoverCatalogScenario,
  getAppBaseURL,
  gotoAppPage,
  gotoSearchPage,
  loginToApp,
  runSearch,
  waitForSearchResponse,
} from './helpers';

async function saveScreenshot(page: Page, testInfo: TestInfo, fileName: string) {
  const screenshotPath = testInfo.outputPath(fileName);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(fileName, { path: screenshotPath, contentType: 'image/png' });
}

async function captureUnauthenticatedLoginPage(browser: Browser, appBaseURL: string, testInfo: TestInfo): Promise<void> {
  const context = await browser.newContext({ storageState: undefined });
  const page = await context.newPage();

  try {
    await page.goto(new URL('/login', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.login-title')).toHaveText('Sign in to Aithena');
    await saveScreenshot(page, testInfo, 'login-page.png');
  } finally {
    await context.close();
  }
}

test('captures curated screenshots for release documentation', async ({ browser, page, request }, testInfo) => {
  test.slow();

  const appBaseURL = getAppBaseURL();
  const catalog = await discoverCatalogScenario(request, appBaseURL);
  test.skip(catalog.totalDocuments === 0, 'At least one indexed document is required for the search results screenshot.');

  await page.setViewportSize({ width: 1440, height: 1024 });

  await test.step('capture login page', async () => {
    await captureUnauthenticatedLoginPage(browser, appBaseURL, testInfo);
  });

  await loginToApp(page, appBaseURL);

  const screenshotQuery =
    catalog.highlightScenario?.query || catalog.pdfScenario?.query || catalog.multiPagePdfScenario?.query || catalog.broadQuery;

  await test.step('capture search empty state', async () => {
    await gotoSearchPage(page, appBaseURL);
    await expect(page.locator('.search-empty')).toBeVisible({ timeout: 10_000 });
    await saveScreenshot(page, testInfo, 'search-empty.png');
  });

  await test.step('capture search results page', async () => {
    await gotoSearchPage(page, appBaseURL);
    await runSearch(page, screenshotQuery);
    await expect(page.locator('.book-card').first()).toBeVisible();
    await saveScreenshot(page, testInfo, 'search-results-page.png');
  });

  await test.step('capture search with facet filter', async () => {
    if (!catalog.facetScenario) {
      test.info().annotations.push({ type: 'warning', description: 'No meaningful facet found — faceted search screenshot skipped.' });
      return;
    }

    await gotoSearchPage(page, appBaseURL);
    await runSearch(page, catalog.facetScenario.query);
    await expect(page.locator('.book-card').first()).toBeVisible();

    const facetItem = page.locator('.facet-panel .facet-item').filter({
      hasText: catalog.facetScenario.author,
    }).first();
    await expect(facetItem).toBeVisible();

    const filterResponsePromise = waitForSearchResponse(
      page,
      (url) => url.searchParams.has('fq_author')
    );

    await facetItem.locator('.facet-label').click();
    await filterResponsePromise;

    await expect(page.locator('.book-card').first()).toBeVisible();
    await saveScreenshot(page, testInfo, 'search-faceted.png');
  });

  await test.step('capture PDF viewer', async () => {
    if (!catalog.pdfScenario) {
      test.info().annotations.push({ type: 'warning', description: 'No PDF document found — PDF viewer screenshot skipped.' });
      return;
    }

    await gotoSearchPage(page, appBaseURL);
    await runSearch(page, catalog.pdfScenario.query);
    await expect(page.locator('.book-card').first()).toBeVisible();

    // Find the card matching the discovered PDF and click its Open PDF button
    const pdfCard = page.locator('.book-card').filter({
      hasText: catalog.pdfScenario.result.title,
    }).first();
    await pdfCard.locator('.open-pdf-btn').click();

    await expect(page.locator('.pdf-viewer-overlay')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.pdf-viewer-panel')).toBeVisible();

    // Allow time for the PDF iframe to begin loading
    await page.waitForTimeout(2_000);
    await saveScreenshot(page, testInfo, 'pdf-viewer.png');
  });

  await test.step('capture similar books panel', async () => {
    // This step depends on the PDF viewer being open from the previous step.
    // If there is no PDF scenario, the viewer was never opened.
    if (!catalog.pdfScenario) {
      test.info().annotations.push({ type: 'warning', description: 'No PDF document available — similar books screenshot skipped.' });
      return;
    }

    try {
      await expect(page.locator('.similar-books-panel')).toBeVisible({ timeout: 15_000 });

      // Wait for similar books to finish loading (loading indicator disappears or cards appear)
      await expect(
        page.locator('.similar-book-card').first().or(page.locator('.similar-books-message'))
      ).toBeVisible({ timeout: 15_000 });

      await saveScreenshot(page, testInfo, 'similar-books.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Similar books panel did not render — screenshot skipped.' });
    }

    // Close the PDF viewer for subsequent steps
    const closeButton = page.locator('.pdf-viewer-close');
    if (await closeButton.isVisible()) {
      await closeButton.click();
      await expect(page.locator('.pdf-viewer-overlay')).not.toBeVisible({ timeout: 10_000 });
    }
  });

  // Ensure the PDF viewer is fully dismissed before navigating to other pages.
  // The close animation may not have completed in the previous step.
  await expect(page.locator('.pdf-viewer-overlay')).not.toBeVisible({ timeout: 5_000 }).catch(() => {});

  await test.step('capture admin dashboard', async () => {
    try {
      await page.locator('a.tab-nav-link[href="/admin"]').click({ timeout: 15_000 });
      await expect(page).toHaveURL(/\/admin$/);
      // The admin API call may fail in CI (e.g. Redis not seeded), which can
      // trigger the auth-failure handler and redirect to /login.  Tolerate this
      // so the screenshot suite is not fragile.
      await expect(page.locator('.admin-title')).toContainText('Admin Dashboard', { timeout: 15_000 });
      await saveScreenshot(page, testInfo, 'admin-dashboard.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Admin page did not render — screenshot skipped.' });
    }
  });

  await test.step('capture upload page', async () => {
    try {
      await gotoAppPage(page, appBaseURL, '/upload');
      await expect(page.locator('.upload-title')).toHaveText('Upload PDF', { timeout: 10_000 });
      await saveScreenshot(page, testInfo, 'upload-page.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Upload page did not render — screenshot skipped.' });
    }
  });

  await test.step('capture status page', async () => {
    try {
      await gotoAppPage(page, appBaseURL, '/status');
      await expect(page.locator('.status-title')).toBeVisible({ timeout: 10_000 });
      await saveScreenshot(page, testInfo, 'status-page.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Status page did not render — screenshot skipped.' });
    }
  });

  await test.step('capture stats page', async () => {
    try {
      await gotoAppPage(page, appBaseURL, '/stats');
      await expect(page.locator('.stats-page-title')).toBeVisible({ timeout: 10_000 });
      await saveScreenshot(page, testInfo, 'stats-page.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Stats page did not render — screenshot skipped.' });
    }
  });

  await test.step('capture library page', async () => {
    try {
      await gotoAppPage(page, appBaseURL, '/library');
      await expect(page.locator('.page-title')).toBeVisible({ timeout: 10_000 });
      await saveScreenshot(page, testInfo, 'library-page.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Library page did not render — screenshot skipped.' });
    }
  });
});
