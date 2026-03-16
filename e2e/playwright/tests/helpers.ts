import { APIRequestContext, expect, Page } from '@playwright/test';

const DEV_UI_PORTS = new Set(['3000', '4173', '4174', '5173', '5174']);
const BROAD_QUERY = '*';
const LOGIN_USERNAME = process.env.E2E_USERNAME || 'admin';
const LOGIN_PASSWORD = process.env.E2E_PASSWORD || 'admin';
let cachedApiAuthHeaders: Record<string, string> | null = null;
const HIGHLIGHT_QUERY_CANDIDATES = [
  'amades',
  'etnologia',
  'barcelona',
  'costumari',
  'balearics',
  'historia',
  'ocr',
];
const MAX_VISIBLE_CARD_ASSERTIONS = 5;

export interface FacetValue {
  value: string;
  count: number;
}

export interface SearchResult {
  id: string;
  title: string;
  author?: string;
  category?: string;
  language?: string;
  page_count?: number;
  file_path?: string;
  document_url?: string | null;
  highlights?: string[];
}

export interface SearchResponse {
  query: string;
  total: number;
  limit: number;
  page: number;
  results: SearchResult[];
  facets: {
    author?: FacetValue[];
    category?: FacetValue[];
    language?: FacetValue[];
    year?: FacetValue[];
  };
}

export interface SearchScenario {
  query: string;
  result: SearchResult;
}

export interface FacetScenario {
  query: string;
  author: string;
  baselineTotal: number;
  filteredTotal: number;
}

export interface CatalogScenario {
  appBaseURL: string;
  apiBaseURL: string;
  broadQuery: string;
  totalDocuments: number;
  highlightScenario?: SearchScenario;
  facetScenario?: FacetScenario;
  pdfScenario?: SearchScenario;
  multiPagePdfScenario?: SearchScenario;
  paginationQuery?: string;
}

export function getAppBaseURL(): string {
  return normalizeUrl(process.env.PLAYWRIGHT_APP_BASE_URL || process.env.BASE_URL || 'http://localhost');
}

export function getApiBaseURL(appBaseURL: string): string {
  const url = new URL(appBaseURL);
  const isLocalhost = url.hostname === 'localhost' || url.hostname === '127.0.0.1';

  if (isLocalhost && DEV_UI_PORTS.has(url.port)) {
    url.port = '8080';
    return normalizeUrl(url.toString());
  }

  return normalizeUrl(url.origin);
}

export async function loginToApp(page: Page, appBaseURL: string): Promise<void> {
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

export async function gotoAppPage(page: Page, appBaseURL: string, path = '/search'): Promise<void> {
  await page.goto(new URL(path, `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });

  const loginVisible = await page.locator('.login-title').isVisible().catch(() => false);
  if (loginVisible) {
    await loginToApp(page, appBaseURL);
    if (path !== '/search') {
      await page.goto(new URL(path, `${appBaseURL}/`).toString(), { waitUntil: 'domcontentloaded' });
    }
  }

  await expect(page.locator('h1.sidebar-title')).toHaveText(/Aithena/);
}

export async function gotoSearchPage(page: Page, appBaseURL: string): Promise<void> {
  await gotoAppPage(page, appBaseURL, '/search');
  await expect(page.locator('input.search-input')).toBeVisible();
}

export async function waitForSearchResponse(
  page: Page,
  matcher: (url: URL) => boolean
) {
  return page.waitForResponse(
    (response) => {
      if (response.request().method() !== 'GET' || !response.url().includes('/v1/search')) {
        return false;
      }

      try {
        return matcher(new URL(response.url()));
      } catch {
        return false;
      }
    },
    { timeout: 20_000 }
  );
}

export async function runSearch(page: Page, query: string): Promise<void> {
  await page.locator('input.search-input').fill(query);
  const responsePromise = waitForSearchResponse(
    page,
    (url) => url.searchParams.get('q') === query && url.searchParams.get('page') === '1'
  );

  await page.locator('button.search-btn').click();
  const response = await responsePromise;

  if (!response.ok()) {
    throw new Error(`Search request failed for ${query}: ${response.status()} ${response.url()}`);
  }

  await expect(page.locator('button.search-btn')).toHaveText('Search');
  await expect(page.locator('.search-result-count')).toContainText(`"${query}"`);
}

export async function getVisibleTitles(page: Page): Promise<string[]> {
  const titles = await page.locator('.book-card .book-title').allTextContents();
  return titles.map((title) => title.trim()).filter(Boolean);
}

export async function getResultCount(page: Page): Promise<number> {
  const text = (await page.locator('.search-result-count').textContent()) || '';
  const match = text.match(/([\d,]+)\s+result/);

  if (!match) {
    throw new Error(`Could not parse result count from: ${text}`);
  }

  return Number(match[1].replace(/,/g, ''));
}

export async function expectVisibleCardsToMatchAuthor(page: Page, author: string): Promise<void> {
  const cards = page.locator('.book-card');
  const count = Math.min(await cards.count(), MAX_VISIBLE_CARD_ASSERTIONS);

  for (let index = 0; index < count; index += 1) {
    await expect(cards.nth(index).locator('.book-meta')).toContainText(author);
  }
}

async function getApiAuthHeaders(request: APIRequestContext, apiBaseURL: string): Promise<Record<string, string>> {
  if (cachedApiAuthHeaders) {
    return cachedApiAuthHeaders;
  }

  const response = await request.post(`${apiBaseURL}/v1/auth/login`, {
    data: { username: LOGIN_USERNAME, password: LOGIN_PASSWORD },
    timeout: 15_000,
  });

  if (!response.ok()) {
    throw new Error(`API login failed (${response.status()}) at ${response.url()}: ${await response.text()}`);
  }

  const payload = (await response.json()) as { access_token?: string };
  if (!payload.access_token) {
    throw new Error(`API login response missing access_token: ${JSON.stringify(payload)}`);
  }

  cachedApiAuthHeaders = { Authorization: `Bearer ${payload.access_token}` };
  return cachedApiAuthHeaders;
}

export async function discoverCatalogScenario(
  request: APIRequestContext,
  appBaseURL: string
): Promise<CatalogScenario> {
  const apiBaseURL = getApiBaseURL(appBaseURL);
  const searchCache = new Map<string, SearchResponse>();
  const authHeaders = await getApiAuthHeaders(request, apiBaseURL);

  const search = async (
    query: string,
    extraParams: Record<string, string> = {},
    limit = 25
  ): Promise<SearchResponse> => {
    const cacheKey = JSON.stringify({ query, extraParams, limit });
    const cached = searchCache.get(cacheKey);
    if (cached) {
      return cached;
    }

    const response = await request.get(`${apiBaseURL}/v1/search/`, {
      params: {
        q: query,
        page: '1',
        limit: String(limit),
        ...extraParams,
      },
      headers: authHeaders,
      timeout: 15_000,
    });

    if (!response.ok()) {
      throw new Error(
        `Search discovery failed (${response.status()}) at ${response.url()}: ${await response.text()}`
      );
    }

    const payload = (await response.json()) as SearchResponse;
    searchCache.set(cacheKey, payload);
    return payload;
  };

  const broad = await search(BROAD_QUERY, {}, 50);
  const scenario: CatalogScenario = {
    appBaseURL,
    apiBaseURL,
    broadQuery: BROAD_QUERY,
    totalDocuments: broad.total,
    paginationQuery: broad.total > 10 ? BROAD_QUERY : undefined,
  };

  if (broad.total === 0) {
    return scenario;
  }

  const candidateQueries = Array.from(
    new Set([...HIGHLIGHT_QUERY_CANDIDATES, ...extractCandidateQueries(broad.results)])
  );

  for (const query of candidateQueries) {
    const response = await search(query, {}, 10);
    const highlighted = response.results.find(
      (result) => Boolean(result.author) && Boolean(result.highlights?.length)
    );

    if (!scenario.highlightScenario && highlighted) {
      scenario.highlightScenario = { query, result: highlighted };
    }

    const pdfResult = response.results.find((result) => Boolean(result.document_url));
    if (!scenario.pdfScenario && pdfResult) {
      scenario.pdfScenario = { query, result: pdfResult };
    }

    const multiPagePdfResult = response.results.find(
      (result) => Boolean(result.document_url) && (result.page_count ?? 0) > 1
    );
    if (!scenario.multiPagePdfScenario && multiPagePdfResult) {
      scenario.multiPagePdfScenario = { query, result: multiPagePdfResult };
    }

    if (scenario.highlightScenario && scenario.pdfScenario && scenario.multiPagePdfScenario) {
      break;
    }
  }

  if (!scenario.pdfScenario) {
    const fallbackPdf = broad.results.find((result) => Boolean(result.document_url));
    if (fallbackPdf) {
      scenario.pdfScenario = { query: BROAD_QUERY, result: fallbackPdf };
    }
  }

  if (!scenario.multiPagePdfScenario) {
    const fallbackMultiPagePdf = broad.results.find(
      (result) => Boolean(result.document_url) && (result.page_count ?? 0) > 1
    );
    if (fallbackMultiPagePdf) {
      scenario.multiPagePdfScenario = { query: BROAD_QUERY, result: fallbackMultiPagePdf };
    }
  }

  const meaningfulAuthorFacet = (broad.facets.author || []).find(
    (facet) => facet.value && facet.count > 0 && facet.count < broad.total
  );

  if (meaningfulAuthorFacet) {
    const filtered = await search(
      BROAD_QUERY,
      { fq_author: meaningfulAuthorFacet.value },
      10
    );

    if (filtered.total > 0) {
      scenario.facetScenario = {
        query: BROAD_QUERY,
        author: meaningfulAuthorFacet.value,
        baselineTotal: broad.total,
        filteredTotal: filtered.total,
      };
    }
  }

  return scenario;
}

function extractCandidateQueries(results: SearchResult[]): string[] {
  const candidates = new Set<string>();

  for (const result of results) {
    for (const source of [result.title, result.author, result.category]) {
      if (!source) {
        continue;
      }

      for (const token of source.split(/[^\p{L}\p{N}]+/u)) {
        const normalized = token.trim();
        if (
          normalized.length >= 4 &&
          !/^\d+$/.test(normalized) &&
          normalized.toLowerCase() !== 'unknown'
        ) {
          candidates.add(normalized);
        }
      }
    }

    if (candidates.size >= 20) {
      break;
    }
  }

  return [...candidates];
}

function normalizeUrl(url: string): string {
  return url.replace(/\/+$/, '');
}
