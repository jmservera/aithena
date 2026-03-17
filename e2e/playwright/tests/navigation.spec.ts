import { test, expect } from '@playwright/test';

import { getAppBaseURL, gotoAppPage, gotoSearchPage } from './helpers';

let appBaseURL = '';

test.beforeAll(() => {
  appBaseURL = getAppBaseURL();
});

test('renders the empty search state before any query is submitted', async ({ page }) => {
  await gotoSearchPage(page, appBaseURL);

  await expect(page.locator('.search-empty')).toHaveText('Enter a search term above to find books.');
  await expect(page.locator('.book-card')).toHaveCount(0);
});

test('navigates across the Search, Library, Status, and Stats tabs', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/search');

  const cases = [
    {
      path: '/search',
      assertion: async () => {
        await expect(page.locator('input.search-input')).toBeVisible();
      },
    },
    {
      path: '/library',
      selector: '.page-title',
      text: '📖 Library',
    },
    {
      path: '/status',
      selector: '.status-title',
      text: '🟢 System Status',
    },
    {
      path: '/stats',
      selector: '.stats-page-title',
      text: '📊 Collection Stats',
    },
  ] as const;

  for (const testCase of cases) {
    await page.locator(`a.tab-nav-link[href="${testCase.path}"]`).click();
    await expect(page).toHaveURL(new RegExp(`${testCase.path}$`));
    await expect(page.locator(`a.tab-nav-link[href="${testCase.path}"]`)).toHaveClass(
      /tab-nav-link--active/
    );

    if ('assertion' in testCase) {
      await testCase.assertion();
      continue;
    }

    if ('selector' in testCase) {
      await expect(page.locator(testCase.selector)).toHaveText(testCase.text);
      continue;
    }

    await expect(page.locator('.placeholder-title')).toHaveText(testCase.heading);
    await expect(page.locator('.placeholder-subtitle')).toHaveText(testCase.subtitle);
  }
});
