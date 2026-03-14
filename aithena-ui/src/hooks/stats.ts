import { useState, useEffect } from 'react';

import { buildApiUrl } from '../api';

const statsUrl = buildApiUrl('/v1/stats/');

export interface FacetEntry {
  value: string;
  count: number;
}

export interface PageStats {
  total: number;
  avg: number;
  min: number;
  max: number;
}

export interface StatsResponse {
  total_books: number;
  by_language: FacetEntry[];
  by_author: FacetEntry[];
  by_year: FacetEntry[];
  by_category: FacetEntry[];
  page_stats: PageStats;
}

export interface UseStatsResult {
  stats: StatsResponse | null;
  loading: boolean;
  error: string | null;
}

export function useStats(): UseStatsResult {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchStats() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(statsUrl);
        if (!response.ok) {
          throw new Error(`Stats request failed: ${response.status}`);
        }
        const data: StatsResponse = await response.json();
        if (!cancelled) {
          setStats(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load stats');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchStats();
    return () => {
      cancelled = true;
    };
  }, []);

  return { stats, loading, error };
}
