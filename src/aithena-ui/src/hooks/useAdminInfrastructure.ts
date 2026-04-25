import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, buildApiUrl } from '../api';

/* ── API response types ───────────────────────────────────────────────── */

export interface ServiceEndpoint {
  name: string;
  url: string;
  status: string;
  type: string;
}

export interface InfrastructureInfo {
  services: ServiceEndpoint[];
  solr_admin_url: string;
  rabbitmq_admin_url: string;
  redis_admin_url: string;
}

/* ── Hook state ───────────────────────────────────────────────────────── */

export interface UseAdminInfrastructureReturn {
  data: InfrastructureInfo | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

async function fetchInfrastructure(): Promise<InfrastructureInfo> {
  const response = await apiFetch(buildApiUrl('/v1/admin/infrastructure'));
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
  return (await response.json()) as InfrastructureInfo;
}

export function useAdminInfrastructure(): UseAdminInfrastructureReturn {
  const [data, setData] = useState<InfrastructureInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialFetchDone = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchInfrastructure();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load infrastructure');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialFetchDone.current) return;
    initialFetchDone.current = true;

    let cancelled = false;

    fetchInfrastructure()
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load infrastructure');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    setLoading(true);

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error, refresh };
}
