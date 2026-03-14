import { useState, useEffect, useCallback } from "react";

import { buildApiUrl } from "../api";

const searchBaseURL = buildApiUrl("/v1/search");

export interface BookResult {
  id: string;
  title: string;
  author?: string;
  category?: string;
  year?: number;
  language?: string;
  page_count?: number;
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

export type SearchMode = "keyword" | "semantic" | "hybrid";

export interface SearchResponse {
  results: BookResult[];
  total: number;
  query: string;
  facets: FacetGroups;
  page: number;
  limit: number;
}

export interface SearchState {
  query: string;
  filters: SearchFilters;
  page: number;
  limit: number;
  sort: string;
  mode: SearchMode;
}

const defaultSearchState: SearchState = {
  query: "",
  filters: {},
  page: 1,
  limit: 10,
  sort: "score desc",
  mode: "keyword",
};

export function useSearch() {
  const [searchState, setSearchState] =
    useState<SearchState>(defaultSearchState);
  const [results, setResults] = useState<BookResult[]>([]);
  const [facets, setFacets] = useState<FacetGroups>({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async (state: SearchState) => {
    if (!state.query.trim()) {
      setResults([]);
      setFacets({});
      setTotal(0);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("q", state.query);
      params.set("limit", state.limit.toString());
      params.set("page", state.page.toString());
      params.set("sort", state.sort);
      params.set("mode", state.mode);

      if (state.filters.author) params.set("fq_author", state.filters.author);
      if (state.filters.category)
        params.set("fq_category", state.filters.category);
      if (state.filters.language)
        params.set("fq_language", state.filters.language);
      if (state.filters.year) params.set("fq_year", state.filters.year);

      const response = await fetch(`${searchBaseURL}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Search request failed: ${response.status}`);
      }
      const data: SearchResponse = await response.json();
      setResults(data.results ?? []);
      setFacets(data.facets ?? {});
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
      setFacets({});
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runSearch(searchState);
  }, [searchState, runSearch]);

  const submitSearch = useCallback((query: string, mode: SearchMode = "keyword") => {
    setSearchState((prev) => ({ ...prev, query, mode, page: 1 }));
  }, []);

  const setQuery = useCallback((query: string) => {
    submitSearch(query, "keyword");
  }, [submitSearch]);

  const setFilter = useCallback(
    (key: keyof SearchFilters, value: string | undefined) => {
      setSearchState((prev) => ({
        ...prev,
        page: 1,
        filters: { ...prev.filters, [key]: value },
      }));
    },
    []
  );

  const clearFilters = useCallback(() => {
    setSearchState((prev) => ({ ...prev, page: 1, filters: {} }));
  }, []);

  const setPage = useCallback((page: number) => {
    setSearchState((prev) => ({ ...prev, page }));
  }, []);

  const setSort = useCallback((sort: string) => {
    setSearchState((prev) => ({ ...prev, sort, page: 1 }));
  }, []);

  const setLimit = useCallback((limit: number) => {
    setSearchState((prev) => ({ ...prev, limit, page: 1 }));
  }, []);

  return {
    searchState,
    results,
    facets,
    total,
    loading,
    error,
    submitSearch,
    setQuery,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
  };
}
