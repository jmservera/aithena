import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, buildApiUrl } from '../api';

const REFRESH_INTERVAL_MS = 30_000;
const STALE_THRESHOLD_MS = 30_000;

/* ── API response types ───────────────────────────────────────────────── */

export interface ContainerInfo {
  name: string;
  status: string;
  type: string;
  version?: string;
  commit?: string;
  last_updated?: string;
}

export interface ContainersResponse {
  containers: ContainerInfo[];
  total: number;
  healthy: number;
  last_updated: string;
}

/* ── Hook state ───────────────────────────────────────────────────────── */

export interface AdminSystemStatusState {
  data: ContainersResponse | null;
  loading: boolean;
  error: string | null;
  lastRefreshed: Date | null;
  isStale: boolean;
}

export interface UseAdminSystemStatusReturn extends AdminSystemStatusState {
  refresh: () => Promise<void>;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await apiFetch(url);
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
  return (await response.json()) as T;
}

export function useAdminSystemStatus(): UseAdminSystemStatusReturn {
  const [data, setData] = useState<ContainersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const staleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchJson<ContainersResponse>(buildApiUrl('/v1/admin/containers'));
      setData(result);
      setError(null);
      setLastRefreshed(new Date());
      setIsStale(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load system status');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + auto-refresh
  useEffect(() => {
    let cancelled = false;

    const doFetch = async () => {
      if (!cancelled) await refresh();
    };

    doFetch();
    intervalRef.current = setInterval(doFetch, REFRESH_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [refresh]);

  // Stale data indicator
  useEffect(() => {
    if (!lastRefreshed) return;

    const checkStale = () => {
      const elapsed = Date.now() - lastRefreshed.getTime();
      setIsStale(elapsed >= STALE_THRESHOLD_MS);
    };

    staleRef.current = setInterval(checkStale, 5_000);
    return () => {
      if (staleRef.current) {
        clearInterval(staleRef.current);
        staleRef.current = null;
      }
    };
  }, [lastRefreshed]);

  return { data, loading, error, lastRefreshed, isStale, refresh };
}
