/**
 * useSearchState — sync SearchState with URL query parameters.
 *
 * Reads initial state from the URL (deep-linking), writes back on every
 * change, and supports browser back / forward navigation.
 *
 * Default-valued params are omitted from the URL to keep it clean:
 *   /search?q=react              (page 1, sort=relevance, mode=keyword, limit=10)
 *   /search?q=react&page=3&sort=year_i+desc&filter_author=Doe
 */
import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { SearchState, SearchFilters, SearchMode } from './search';

// -- Validation sets --

const VALID_MODES: readonly SearchMode[] = ['keyword', 'semantic', 'hybrid'];

const VALID_SORT_VALUES: readonly string[] = [
  'score desc',
  'year_i desc',
  'year_i asc',
  'title_s asc',
  'author_s asc',
];

const VALID_LIMITS: readonly number[] = [10, 20, 50];

const FILTER_KEYS: readonly (keyof SearchFilters)[] = ['author', 'category', 'language', 'year'];

// -- Defaults (exported so tests / other hooks can reference them) --

export const DEFAULTS: Readonly<SearchState> = {
  query: '',
  filters: {},
  page: 1,
  limit: 10,
  sort: 'score desc',
  mode: 'keyword',
};

// -- URL <-> State mappers --

/** Parse URL search params into a validated SearchState. */
export function parseSearchParams(params: URLSearchParams): SearchState {
  const query = params.get('q') ?? '';

  const rawPage = Number(params.get('page'));
  const page = Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;

  const rawLimit = Number(params.get('limit'));
  const limit = VALID_LIMITS.includes(rawLimit) ? rawLimit : DEFAULTS.limit;

  const rawSort = params.get('sort') ?? '';
  const sort = VALID_SORT_VALUES.includes(rawSort) ? rawSort : DEFAULTS.sort;

  const rawMode = params.get('mode') ?? '';
  const mode = VALID_MODES.includes(rawMode as SearchMode)
    ? (rawMode as SearchMode)
    : DEFAULTS.mode;

  const filters: SearchFilters = {};
  for (const key of FILTER_KEYS) {
    const value = params.get(`filter_${key}`);
    if (value) {
      filters[key] = value;
    }
  }

  return { query, filters, page, limit, sort, mode };
}

/** Serialise SearchState to URL params, omitting defaults for clean URLs. */
export function stateToParams(state: SearchState): URLSearchParams {
  const params = new URLSearchParams();

  if (state.query) params.set('q', state.query);
  if (state.page > 1) params.set('page', String(state.page));
  if (state.sort !== DEFAULTS.sort) params.set('sort', state.sort);
  if (state.mode !== DEFAULTS.mode) params.set('mode', state.mode);
  if (state.limit !== DEFAULTS.limit) params.set('limit', String(state.limit));

  for (const key of FILTER_KEYS) {
    const value = state.filters[key];
    if (value) {
      params.set(`filter_${key}`, value);
    }
  }

  return params;
}

// -- Hook --

export type NavigateMode = 'push' | 'replace';

export type SearchStateSetter = (
  update: SearchState | ((prev: SearchState) => SearchState),
  mode?: NavigateMode
) => void;

/**
 * Drop-in replacement for useState<SearchState> that is backed by URL
 * search parameters.  The returned setter accepts an optional second argument
 * to choose between push (new history entry) and replace (default).
 */
export function useSearchState(): [SearchState, SearchStateSetter] {
  const [searchParams, setSearchParams] = useSearchParams();

  const searchState = useMemo(() => parseSearchParams(searchParams), [searchParams]);

  const setSearchState: SearchStateSetter = useCallback(
    (update, mode: NavigateMode = 'replace') => {
      setSearchParams(
        (prev) => {
          const prevState = parseSearchParams(prev);
          const nextState = typeof update === 'function' ? update(prevState) : update;
          return stateToParams(nextState);
        },
        { replace: mode === 'replace' }
      );
    },
    [setSearchParams]
  );

  return [searchState, setSearchState];
}
