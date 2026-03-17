import { expect, test, type Browser, type Page, type TestInfo } from '@playwright/test';

import { discoverCatalogScenario, getAppBaseURL, gotoSearchPage, loginToApp, runSearch } from './helpers';

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

  await test.step('capture search results page', async () => {
    await gotoSearchPage(page, appBaseURL);
    await runSearch(page, screenshotQuery);
    await expect(page.locator('.book-card').first()).toBeVisible();
    await saveScreenshot(page, testInfo, 'search-results-page.png');
  });

  await test.step('capture admin dashboard', async () => {
    await page.locator('a.tab-nav-link[href="/admin"]').click();
    await expect(page).toHaveURL(/\/admin$/);
    // The admin API call may fail in CI (e.g. Redis not seeded), which can
    // trigger the auth-failure handler and redirect to /login.  Tolerate this
    // so the screenshot suite is not fragile.
    try {
      await expect(page.locator('.admin-title')).toHaveText('🏛️ Admin Dashboard', { timeout: 15_000 });
      await saveScreenshot(page, testInfo, 'admin-dashboard.png');
    } catch {
      test.info().annotations.push({ type: 'warning', description: 'Admin page did not render — screenshot skipped.' });
    }
  });

  await test.step('capture upload page', async () => {
    await page.goto(new URL('/upload', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.upload-title')).toHaveText('Upload PDF');
    await saveScreenshot(page, testInfo, 'upload-page.png');
  });
});
