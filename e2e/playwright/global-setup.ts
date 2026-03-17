import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { request as playwrightRequest, type FullConfig } from '@playwright/test';

const DEFAULT_BASE_URL = process.env.BASE_URL || 'http://localhost';
const FALLBACK_BASE_URL = process.env.FALLBACK_BASE_URL || 'http://localhost:5173';
const DEFAULT_SEARCH_API_URL = process.env.SEARCH_API_URL || 'http://localhost:8080';
const APP_READY_TIMEOUT_MS = Number(process.env.APP_READY_TIMEOUT_MS || '90000');
const AUTH_TOKEN_STORAGE_KEY = 'aithena.auth.token';
const AUTH_DIR = path.resolve(__dirname, '.auth');
const AUTH_STATE_PATH = path.join(AUTH_DIR, 'state.json');

interface LoginResponse {
  access_token?: string;
}

function normalizeUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

function isAppHtml(body: string): boolean {
  return body.includes('id="root"') || body.includes('Aithena');
}

function getApiBaseUrl(appBaseURL: string): string {
  if (process.env.SEARCH_API_URL) {
    return normalizeUrl(process.env.SEARCH_API_URL);
  }

  const apiUrl = new URL(appBaseURL);
  apiUrl.port = '8080';
  return normalizeUrl(apiUrl.toString());
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

async function writeAuthStorageState(resolvedBaseURL: string): Promise<void> {
  const username = process.env.E2E_USERNAME || process.env.CI_ADMIN_USERNAME;
  const password = process.env.E2E_PASSWORD || process.env.CI_ADMIN_PASSWORD;

  if (!username || !password) {
    throw new Error(
      'Missing Playwright E2E credentials. Set E2E_USERNAME/E2E_PASSWORD or CI_ADMIN_USERNAME/CI_ADMIN_PASSWORD.'
    );
  }

  const apiBaseURL = getApiBaseUrl(resolvedBaseURL) || DEFAULT_SEARCH_API_URL;
  const api = await playwrightRequest.newContext({ ignoreHTTPSErrors: true });

  try {
    const response = await api.post(new URL('/v1/auth/login', `${apiBaseURL}/`).toString(), {
      data: { username, password },
      timeout: 15_000,
    });

    if (!response.ok()) {
      throw new Error(`API login failed (${response.status()}) at ${response.url()}: ${await response.text()}`);
    }

    const payload = (await response.json()) as LoginResponse;
    if (!payload.access_token) {
      throw new Error(`API login response missing access_token: ${JSON.stringify(payload)}`);
    }

    await mkdir(AUTH_DIR, { recursive: true });
    await writeFile(
      AUTH_STATE_PATH,
      JSON.stringify(
        {
          cookies: [],
          origins: [
            {
              origin: resolvedBaseURL,
              localStorage: [{ name: AUTH_TOKEN_STORAGE_KEY, value: payload.access_token }],
            },
          ],
        },
        null,
        2
      )
    );
  } finally {
    await api.dispose();
  }
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  const resolvedBaseURL = await findAvailableAppUrl();
  process.env.PLAYWRIGHT_APP_BASE_URL = resolvedBaseURL;
  await writeAuthStorageState(resolvedBaseURL);
  console.log(`[playwright] using app base URL: ${resolvedBaseURL}`);
  console.log(`[playwright] using search API URL: ${getApiBaseUrl(resolvedBaseURL) || DEFAULT_SEARCH_API_URL}`);
  console.log(`[playwright] wrote auth storage state: ${AUTH_STATE_PATH}`);
}
