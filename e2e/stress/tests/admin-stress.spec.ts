/**
 * Admin stress test — queue monitoring, requeue, and clear under load.
 *
 * Exercises the admin / status dashboard with rapid repeated actions:
 * monitoring queue state, triggering requeue operations, and clearing
 * processed items. Verifies the UI remains stable under pressure.
 */

import { test, expect } from '@playwright/test';

import {
  getAppBaseURL,
  gotoAppPage,
} from '../../playwright/tests/helpers';
import { StressConfig } from '../stress.config';

let appBaseURL = '';

test.beforeAll(() => {
  appBaseURL = getAppBaseURL();
});

test('status page loads consistently under repeated rapid navigation', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/status');

  for (let i = 0; i < StressConfig.admin.actionRepetitions; i++) {
    await page.locator('a.tab-nav-link[href="/search"]').click();
    await expect(page).toHaveURL(/\/search$/);

    await page.locator('a.tab-nav-link[href="/status"]').click();
    await expect(page).toHaveURL(/\/status$/);

    await expect(page.locator('.status-title')).toContainText('System Status');
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('queue monitoring data remains accessible under rapid polling', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/status');

  const statusTitle = page.locator('.status-title');
  const titleVisible = await statusTitle.isVisible().catch(() => false);
  if (!titleVisible) {
    test.skip(true, 'Status page not available — admin UI may not be implemented.');
    return;
  }

  for (let i = 0; i < StressConfig.admin.actionRepetitions; i++) {
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('.status-title')).toContainText('System Status');

    if (StressConfig.admin.delayBetweenMs > 0 && i < StressConfig.admin.actionRepetitions - 1) {
      await page.waitForTimeout(StressConfig.admin.delayBetweenMs);
    }
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('requeue action handles rapid repeated clicks gracefully', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/status');

  const requeueBtn = page
    .locator('button:has-text("Requeue"), button:has-text("Retry"), button:has-text("Reindex")')
    .first();
  const requeueVisible = await requeueBtn.isVisible().catch(() => false);

  if (!requeueVisible) {
    test.skip(true, 'No requeue button found — no failed documents or feature not available.');
    return;
  }

  for (let i = 0; i < StressConfig.admin.actionRepetitions; i++) {
    const btnStillVisible = await requeueBtn.isVisible().catch(() => false);
    if (!btnStillVisible) break;

    await requeueBtn.click();

    const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Yes")').first();
    const confirmVisible = await confirmBtn
      .waitFor({ state: 'visible', timeout: 2_000 })
      .then(() => true)
      .catch(() => false);
    if (confirmVisible) {
      await confirmBtn.click();
    }

    if (StressConfig.admin.delayBetweenMs > 0) {
      await page.waitForTimeout(StressConfig.admin.delayBetweenMs);
    }
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('clear processed action handles rapid repeated clicks gracefully', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/status');

  const clearBtn = page
    .locator('button:has-text("Clear"), button:has-text("Remove processed"), button:has-text("Clean")')
    .first();
  const clearVisible = await clearBtn.isVisible().catch(() => false);

  if (!clearVisible) {
    test.skip(true, 'No clear button found — no processed documents or feature not available.');
    return;
  }

  for (let i = 0; i < StressConfig.admin.actionRepetitions; i++) {
    const btnStillVisible = await clearBtn.isVisible().catch(() => false);
    if (!btnStillVisible) break;

    await clearBtn.click();

    const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Yes")').first();
    const confirmVisible = await confirmBtn
      .waitFor({ state: 'visible', timeout: 2_000 })
      .then(() => true)
      .catch(() => false);
    if (confirmVisible) {
      await confirmBtn.click();
    }

    if (StressConfig.admin.delayBetweenMs > 0) {
      await page.waitForTimeout(StressConfig.admin.delayBetweenMs);
    }
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
});

test('admin workflows remain responsive under rapid tab switching', async ({ page }) => {
  await gotoAppPage(page, appBaseURL, '/search');

  const tabs = ['/search', '/status', '/stats', '/library'] as const;

  for (let cycle = 0; cycle < StressConfig.admin.actionRepetitions; cycle++) {
    for (const tab of tabs) {
      await page.locator(`a.tab-nav-link[href="${tab}"]`).click();
      await expect(page).toHaveURL(new RegExp(`${tab}$`));
    }
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);

  await page.locator('a.tab-nav-link[href="/status"]').click();
  await expect(page.locator('.status-title')).toContainText('System Status');
});
