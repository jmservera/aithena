import { expect, test, type Page, type TestInfo } from '@playwright/test';

import { discoverCatalogScenario, getAppBaseURL, gotoSearchPage, runSearch } from './helpers';

const LOGIN_USERNAME = process.env.E2E_USERNAME || 'admin';
const LOGIN_PASSWORD = process.env.E2E_PASSWORD || 'admin';

async function saveScreenshot(page: Page, testInfo: TestInfo, fileName: string) {
  const screenshotPath = testInfo.outputPath(fileName);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(fileName, { path: screenshotPath, contentType: 'image/png' });
}

async function login(page: Page, appBaseURL: string) {
  await page.goto(new URL('/login', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.login-title')).toHaveText('Sign in to Aithena');
  await page.getByLabel('Username').fill(LOGIN_USERNAME);
  await page.getByLabel('Password').fill(LOGIN_PASSWORD);
  await Promise.all([
    page.waitForURL(/\/search$/, { timeout: 20_000 }),
    page.getByRole('button', { name: 'Sign in' }).click(),
  ]);
  await expect(page.locator('.tab-nav-user')).toContainText(LOGIN_USERNAME);
}

test('captures curated screenshots for release documentation', async ({ page, request }, testInfo) => {
  test.slow();

  const appBaseURL = getAppBaseURL();
  const catalog = await discoverCatalogScenario(request, appBaseURL);
  test.skip(catalog.totalDocuments === 0, 'At least one indexed document is required for the search results screenshot.');

  await page.setViewportSize({ width: 1440, height: 1024 });

  await test.step('capture login page', async () => {
    await page.goto(new URL('/login', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.login-title')).toHaveText('Sign in to Aithena');
    await saveScreenshot(page, testInfo, 'login-page.png');
  });

  await login(page, appBaseURL);

  const screenshotQuery =
    catalog.highlightScenario?.query || catalog.pdfScenario?.query || catalog.multiPagePdfScenario?.query || catalog.broadQuery;

  await test.step('capture search results page', async () => {
    await gotoSearchPage(page, appBaseURL);
    await runSearch(page, screenshotQuery);
    await expect(page.locator('.book-card').first()).toBeVisible();
    await saveScreenshot(page, testInfo, 'search-results-page.png');
  });

  await test.step('capture admin dashboard', async () => {
    await page.goto(new URL('/admin', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.admin-title')).toHaveText('🏛️ Admin Dashboard');
    await saveScreenshot(page, testInfo, 'admin-dashboard.png');
  });

  await test.step('capture upload page', async () => {
    await page.goto(new URL('/upload', `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.upload-title')).toHaveText('Upload PDF');
    await saveScreenshot(page, testInfo, 'upload-page.png');
  });
});
