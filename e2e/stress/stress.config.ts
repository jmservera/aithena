/**
 * Stress test configuration — tuneable parameters for each scenario.
 *
 * Override any value via environment variables. All durations are in milliseconds
 * unless otherwise noted.
 */

function envInt(key: string, fallback: number): number {
  const raw = process.env[key];
  return raw ? parseInt(raw, 10) : fallback;
}

export const StressConfig = {
  /** upload-stress */
  upload: {
    simultaneousFiles: envInt('STRESS_UPLOAD_FILES', 10),
    feedbackTimeoutMs: envInt('STRESS_UPLOAD_TIMEOUT_MS', 30_000),
  },

  /** search-stress */
  search: {
    rapidFireQueries: envInt('STRESS_SEARCH_QUERIES', 20),
    delayBetweenMs: envInt('STRESS_SEARCH_DELAY_MS', 200),
    maxResponseTimeMs: envInt('STRESS_SEARCH_MAX_RESPONSE_MS', 15_000),
  },

  /** admin-stress */
  admin: {
    actionRepetitions: envInt('STRESS_ADMIN_REPETITIONS', 10),
    delayBetweenMs: envInt('STRESS_ADMIN_DELAY_MS', 500),
  },

  /** pagination-stress */
  pagination: {
    maxPagesToTraverse: envInt('STRESS_PAGINATION_MAX_PAGES', 50),
    pageLoadTimeoutMs: envInt('STRESS_PAGINATION_PAGE_TIMEOUT_MS', 20_000),
  },

  /** concurrent-sessions */
  concurrent: {
    browserContexts: envInt('STRESS_CONCURRENT_CONTEXTS', 5),
    actionsPerContext: envInt('STRESS_CONCURRENT_ACTIONS', 10),
  },
} as const;
