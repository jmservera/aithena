import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiFetch, buildApiUrl } from '../api';
import { BookResult, FacetGroups, SearchFilters } from './search';

const libraryBaseURL = buildApiUrl('/v1/books');

export interface LibraryState {
  filters: SearchFilters;
  page: number;
  limit: number;
  sort: string;
}

export interface LibraryResponse {
  results: BookResult[];
  total: number;
  facets: FacetGroups;
  page: number;
  limit: number;
}

const DEFAULTS: Readonly<LibraryState> = {
  filters: {},
  page: 1,
  limit: 20,
  sort: 'title_s asc',
};

function parseLibraryParams(params: URLSearchParams): LibraryState {
  const rawPage = Number(params.get('page'));
  const page = Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : DEFAULTS.page;

  const rawLimit = Number(params.get('limit'));
  const limit = [10, 20, 50].includes(rawLimit) ? rawLimit : DEFAULTS.limit;

  const sort = params.get('sort') || DEFAULTS.sort;

  const filters: SearchFilters = {};
  const author = params.get('fq_author');
  const category = params.get('fq_category');
  const language = params.get('fq_language');
  const year = params.get('fq_year');

  if (author) filters.author = author;
  if (category) filters.category = category;
  if (language) filters.language = language;
  if (year) filters.year = year;

  return { filters, page, limit, sort };
}

function serializeLibraryState(state: LibraryState): URLSearchParams {
  const params = new URLSearchParams();

  if (state.page !== DEFAULTS.page) {
    params.set('page', state.page.toString());
  }

  if (state.limit !== DEFAULTS.limit) {
    params.set('limit', state.limit.toString());
  }

  if (state.sort !== DEFAULTS.sort) {
    params.set('sort', state.sort);
  }

  if (state.filters.author) params.set('fq_author', state.filters.author);
  if (state.filters.category) params.set('fq_category', state.filters.category);
  if (state.filters.language) params.set('fq_language', state.filters.language);
  if (state.filters.year) params.set('fq_year', state.filters.year);

  return params;
}

export function useLibrary() {
  const [searchParams, setSearchParams] = useSearchParams();
  const libraryState = parseLibraryParams(searchParams);

  const [results, setResults] = useState<BookResult[]>([]);
  const [facets, setFacets] = useState<FacetGroups>({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBooks = useCallback(async (state: LibraryState) => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('page', state.page.toString());
      params.set('page_size', state.limit.toString());

      const [sortField, sortOrder] = state.sort.split(' ');
      if (sortField && sortOrder) {
        params.set('sort_by', sortField.replace('_s', '').replace('_i', ''));
        params.set('sort_order', sortOrder);
      }

      if (state.filters.author) params.set('fq_author', state.filters.author);
      if (state.filters.category) params.set('fq_category', state.filters.category);
      if (state.filters.language) params.set('fq_language', state.filters.language);
      if (state.filters.year) params.set('fq_year', state.filters.year);

      const response = await apiFetch(`${libraryBaseURL}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch books: ${response.status}`);
      }
      const data: LibraryResponse = await response.json();
      setResults(data.results ?? []);
      setFacets(data.facets ?? {});
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load books');
      setResults([]);
      setFacets({});
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch books when library state changes - legitimate effect for data fetching
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBooks(libraryState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    libraryState.page,
    libraryState.limit,
    libraryState.sort,
    libraryState.filters.author,
    libraryState.filters.category,
    libraryState.filters.language,
    libraryState.filters.year,
    fetchBooks,
  ]);

  const updateState = useCallback(
    (
      updater: (prev: LibraryState) => LibraryState,
      historyAction: 'push' | 'replace' = 'replace'
    ) => {
      const nextState = updater(libraryState);
      const nextParams = serializeLibraryState(nextState);
      setSearchParams(nextParams, { replace: historyAction === 'replace' });
    },
    [libraryState, setSearchParams]
  );

  const setFilter = useCallback(
    (key: keyof SearchFilters, value: string | undefined) => {
      updateState((prev) => ({
        ...prev,
        page: 1,
        filters: { ...prev.filters, [key]: value },
      }));
    },
    [updateState]
  );

  const clearFilters = useCallback(() => {
    updateState((prev) => ({ ...prev, page: 1, filters: {} }));
  }, [updateState]);

  const setPage = useCallback(
    (page: number) => {
      updateState((prev) => ({ ...prev, page }), 'push');
    },
    [updateState]
  );

  const setSort = useCallback(
    (sort: string) => {
      updateState((prev) => ({ ...prev, sort, page: 1 }));
    },
    [updateState]
  );

  const setLimit = useCallback(
    (limit: number) => {
      updateState((prev) => ({ ...prev, limit, page: 1 }));
    },
    [updateState]
  );

  return {
    libraryState,
    results,
    facets,
    total,
    loading,
    error,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
  };
}
