import { useState, useEffect } from "react";

const statsBaseURL = `${import.meta.env.VITE_API_URL}/v1/stats/`;

export interface StatsBucket {
  value: string;
  count: number;
}

export interface PageStats {
  count: number;
  total_pages: number;
  avg_pages: number;
  min_pages: number;
  max_pages: number;
}

export interface StatsResponse {
  total_books: number;
  by_language: StatsBucket[];
  by_author: StatsBucket[];
  by_year: StatsBucket[];
  by_category: StatsBucket[];
  page_stats: PageStats | Record<string, never>;
}

export function useStats() {
  const [data, setData] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(statsBaseURL)
      .then((res) => {
        if (!res.ok) throw new Error(`Stats request failed: ${res.status}`);
        return res.json() as Promise<StatsResponse>;
      })
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load stats");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error };
}
