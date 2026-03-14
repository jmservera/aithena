import { request as playwrightRequest, type FullConfig } from '@playwright/test';

const DEFAULT_BASE_URL = process.env.BASE_URL || 'http://localhost';
const FALLBACK_BASE_URL = process.env.FALLBACK_BASE_URL || 'http://localhost:5173';
const APP_READY_TIMEOUT_MS = Number(process.env.APP_READY_TIMEOUT_MS || '90000');

function normalizeUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

function isAppHtml(body: string): boolean {
  return body.includes('id="root"') || body.includes('Aithena');
}

async function findAvailableAppUrl(): Promise<string> {
  const candidates = Array.from(new Set([DEFAULT_BASE_URL, FALLBACK_BASE_URL].map(normalizeUrl)));
  const api = await playwrightRequest.newContext({ ignoreHTTPSErrors: true });
  const startedAt = Date.now();
  let lastError = 'No app URL checked yet.';

  try {
    while (Date.now() - startedAt < APP_READY_TIMEOUT_MS) {
      for (const candidate of candidates) {
        try {
          const response = await api.get(new URL('/search', candidate).toString(), {
            timeout: 5_000,
          });
          const body = await response.text();

          if (response.ok() && isAppHtml(body)) {
            return candidate;
          }

          lastError = `${candidate} responded with ${response.status()} but did not look like the app.`;
        } catch (error) {
          lastError = `${candidate} was not reachable: ${error instanceof Error ? error.message : String(error)}`;
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 2_000));
    }
  } finally {
    await api.dispose();
  }

  throw new Error(
    `Timed out after ${APP_READY_TIMEOUT_MS}ms waiting for the Aithena UI. Last error: ${lastError}`
  );
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  const resolvedBaseURL = await findAvailableAppUrl();
  process.env.PLAYWRIGHT_APP_BASE_URL = resolvedBaseURL;
  console.log(`[playwright] using app base URL: ${resolvedBaseURL}`);
}
