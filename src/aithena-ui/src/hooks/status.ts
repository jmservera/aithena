import { useState, useEffect } from 'react';

import { apiFetch, buildApiUrl } from '../api';

const statusUrl = buildApiUrl('/v1/status/');

export interface SolrInfo {
  status: 'ok' | 'degraded' | 'error';
  nodes: number;
  docs_indexed: number;
}

export interface IndexingProgress {
  total_discovered: number;
  indexed: number;
  failed: number;
  pending: number;
}

export interface StatusResponse {
  solr: SolrInfo;
  indexing: IndexingProgress;
  embeddings_available: boolean;
  services: {
    solr: string;
    redis: string;
    rabbitmq: string;
    zookeeper?: string;
    embeddings: string;
  };
}

export interface StatusState {
  data: StatusResponse | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

const REFRESH_INTERVAL_MS = 10_000;

export function useStatus(): StatusState {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    async function fetchStatus() {
      controller = new AbortController();
      try {
        const response = await apiFetch(statusUrl, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Status request failed: ${response.status}`);
        }
        const json: StatusResponse = await response.json();
        if (!cancelled) {
          setData(json);
          setError(null);
          setLastUpdated(new Date());
        }
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === 'AbortError')) {
          setError(err instanceof Error ? err.message : 'Failed to fetch status');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          timeoutId = setTimeout(fetchStatus, REFRESH_INTERVAL_MS);
        }
      }
    }

    fetchStatus();

    return () => {
      cancelled = true;
      controller?.abort();
      clearTimeout(timeoutId);
    };
  }, []);

  return { data, loading, error, lastUpdated };
}
