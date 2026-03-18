import { useState, useEffect, useCallback } from 'react';

import { apiFetch, buildApiUrl } from '../api';
import { useSearchState } from './useSearchState';

const searchBaseURL = buildApiUrl('/v1/search');

export type SearchMode = 'keyword' | 'semantic' | 'hybrid';

export interface BookResult {
  id: string;
  title: string;
  author?: string;
  category?: string;
  year?: number;
  language?: string;
  page_count?: number;
  pages?: [number, number] | null;
  file_path?: string;
  highlights?: string[];
  document_url?: string | null;
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface FacetGroups {
  author?: FacetValue[];
  category?: FacetValue[];
  language?: FacetValue[];
  year?: FacetValue[];
}

export interface SearchFilters {
  author?: string;
  category?: string;
  language?: string;
  year?: string;
}

export interface SearchResponse {
  results: BookResult[];
  total: number;
  query: string;
  facets: FacetGroups;
  page: number;
  limit: number;
  mode?: SearchMode;
}

export interface SearchState {
  query: string;
  filters: SearchFilters;
  page: number;
  limit: number;
  sort: string;
  mode: SearchMode;
}

const modeLabel = (mode: SearchMode) => mode.charAt(0).toUpperCase() + mode.slice(1);

export function useSearch() {
  const [searchState, setSearchState] = useSearchState();
  const [results, setResults] = useState<BookResult[]>([]);
  const [facets, setFacets] = useState<FacetGroups>({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async (state: SearchState) => {
    if (!state.query.trim()) {
      if (state.mode !== 'keyword') {
        setError(`${modeLabel(state.mode)} search requires a search query.`);
        setResults([]);
        setFacets({});
        setTotal(0);
        return;
      }
      setResults([]);
      setFacets({});
      setTotal(0);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('q', state.query);
      params.set('limit', state.limit.toString());
      params.set('page', state.page.toString());
      params.set('sort', state.sort);
      params.set('mode', state.mode);

      if (state.filters.author) params.set('fq_author', state.filters.author);
      if (state.filters.category) params.set('fq_category', state.filters.category);
      if (state.filters.language) params.set('fq_language', state.filters.language);
      if (state.filters.year) params.set('fq_year', state.filters.year);

      const response = await apiFetch(`${searchBaseURL}?${params.toString()}`);
      if (!response.ok) {
        if (response.status === 400 && state.mode !== 'keyword') {
          const body = await response.json().catch(() => ({}));
          const detail =
            typeof body?.detail === 'string'
              ? body.detail
              : `${modeLabel(state.mode)} search is unavailable. Embeddings may not be indexed yet.`;
          throw new Error(detail);
        }
        throw new Error(`Search request failed: ${response.status}`);
      }
      const data: SearchResponse = await response.json();
      setResults(data.results ?? []);
      setFacets(data.facets ?? {});
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
      setFacets({});
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Run search when search state changes - legitimate effect for data fetching
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    runSearch(searchState);
  }, [searchState, runSearch]);

  const setQuery = useCallback(
    (query: string) => {
      setSearchState((prev) => ({ ...prev, query, page: 1 }), 'push');
    },
    [setSearchState]
  );

  const setFilter = useCallback(
    (key: keyof SearchFilters, value: string | undefined) => {
      setSearchState((prev) => ({
        ...prev,
        page: 1,
        filters: { ...prev.filters, [key]: value },
      }));
    },
    [setSearchState]
  );

  const clearFilters = useCallback(() => {
    setSearchState((prev) => ({ ...prev, page: 1, filters: {} }));
  }, [setSearchState]);

  const setPage = useCallback(
    (page: number) => {
      setSearchState((prev) => ({ ...prev, page }), 'push');
    },
    [setSearchState]
  );

  const setSort = useCallback(
    (sort: string) => {
      setSearchState((prev) => ({ ...prev, sort, page: 1 }));
    },
    [setSearchState]
  );

  const setLimit = useCallback(
    (limit: number) => {
      setSearchState((prev) => ({ ...prev, limit, page: 1 }));
    },
    [setSearchState]
  );

  const setMode = useCallback(
    (mode: SearchMode) => {
      setSearchState((prev) => ({ ...prev, mode, page: 1 }));
    },
    [setSearchState]
  );

  return {
    searchState,
    results,
    facets,
    total,
    loading,
    error,
    setQuery,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
    setMode,
  };
}
