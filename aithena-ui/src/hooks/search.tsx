import { useState, useCallback } from "react";

const searchBaseURL = `${import.meta.env.VITE_API_URL}/v1/search/`;

export interface BookResult {
  id: string;
  title: string;
  author: string;
  year?: number;
  snippet?: string;
  file_path?: string;
  document_url?: string;
  category?: string;
  page_count?: number;
}

export interface SearchResponse {
  results: BookResult[];
  total: number;
  query: string;
}

export type SearchState = "idle" | "loading" | "success" | "error";

export const useSearch = () => {
  const [results, setResults] = useState<BookResult[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<SearchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState("");

  const search = useCallback(async (query: string, limit = 10) => {
    if (!query.trim()) {
      setState("idle");
      return;
    }

    setState("loading");
    setError(null);
    setLastQuery(query);

    try {
      const url = new URL(searchBaseURL);
      url.searchParams.set("q", query);
      url.searchParams.set("limit", String(limit));

      const response = await fetch(url.toString(), {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(
          `Search failed: ${response.status} ${response.statusText}`
        );
      }

      const data: SearchResponse = await response.json();
      setResults(data.results ?? []);
      setTotal(data.total ?? data.results?.length ?? 0);
      setState("success");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      );
      setResults([]);
      setTotal(0);
      setState("error");
    }
  }, []);

  const reset = useCallback(() => {
    setResults([]);
    setTotal(0);
    setState("idle");
    setError(null);
    setLastQuery("");
  }, []);

  return { results, total, state, error, lastQuery, search, reset };
};
