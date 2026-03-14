import { useState, useEffect } from 'react';

import { buildApiUrl } from '../api';

const statusUrl = buildApiUrl('/v1/status/');

export interface ServiceHealth {
  status: 'ok' | 'error' | 'degraded';
  reachable: boolean;
  detail?: string;
}

export interface FailedDocument {
  id: string;
  file_path?: string;
  error?: string;
}

export interface IndexingProgress {
  discovered: number;
  indexed: number;
  failed: number;
  pending: number;
}

export interface StatusResponse {
  indexing: IndexingProgress;
  services: {
    solr: ServiceHealth;
    redis: ServiceHealth;
    rabbitmq: ServiceHealth;
  };
  failed_documents: FailedDocument[];
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

    async function fetchStatus() {
      try {
        const response = await fetch(statusUrl);
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
        if (!cancelled) {
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
      clearTimeout(timeoutId);
    };
  }, []);

  return { data, loading, error, lastUpdated };
}
