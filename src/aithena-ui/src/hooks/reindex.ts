import { useState, useCallback } from 'react';
import { apiFetch, buildApiUrl } from '../api';

export interface ReindexResult {
  message: string;
  collection: string;
  solr: string;
  redis_cleared: number;
}

export interface UseAdminReindexReturn {
  loading: boolean;
  error: string | null;
  result: ReindexResult | null;
  triggerReindex: (collection: string) => Promise<void>;
  reset: () => void;
}

export function useAdminReindex(): UseAdminReindexReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReindexResult | null>(null);

  const triggerReindex = useCallback(async (collection: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const url = buildApiUrl(`/v1/admin/reindex?collection=${encodeURIComponent(collection)}`);
      const response = await apiFetch(url, { method: 'POST' });
      if (!response.ok) {
        let detail = `Request failed: ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) detail = String(body.detail);
        } catch {
          // ignore JSON parse errors
        }
        throw new Error(detail);
      }
      const data = (await response.json()) as ReindexResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reindex failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setError(null);
    setResult(null);
  }, []);

  return { loading, error, result, triggerReindex, reset };
}
