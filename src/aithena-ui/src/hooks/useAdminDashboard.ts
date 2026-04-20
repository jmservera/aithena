import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, buildApiUrl } from '../api';

const REFRESH_INTERVAL_MS = 30_000;

/* ── API response types ───────────────────────────────────────────────── */

export interface DocumentMetrics {
  total: number;
  queued: number;
  processed: number;
  failed: number;
}

export interface QueueStatus {
  queue_name: string;
  messages_ready: number;
  messages_unacknowledged: number;
  messages_total: number;
  consumers: number;
  status: string;
}

export interface ContainerInfo {
  name: string;
  status: string;
  type: string;
  version?: string;
  commit?: string;
  last_updated?: string;
}

export interface InfrastructureStatus {
  containers: ContainerInfo[];
  total: number;
  healthy: number;
  last_updated: string;
}

/* ── Hook state ───────────────────────────────────────────────────────── */

export interface AdminDashboardState {
  documents: DocumentMetrics | null;
  queue: QueueStatus | null;
  infrastructure: InfrastructureStatus | null;
  loading: boolean;
  errors: {
    documents: string | null;
    queue: string | null;
    infrastructure: string | null;
  };
  autoRefresh: boolean;
  lastRefreshed: Date | null;
}

export interface UseAdminDashboardReturn extends AdminDashboardState {
  refresh: () => Promise<void>;
  toggleAutoRefresh: () => void;
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

export function useAdminDashboard(): UseAdminDashboardReturn {
  const [documents, setDocuments] = useState<DocumentMetrics | null>(null);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [infrastructure, setInfrastructure] = useState<InfrastructureStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<AdminDashboardState['errors']>({
    documents: null,
    queue: null,
    infrastructure: null,
  });
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const newErrors: AdminDashboardState['errors'] = {
      documents: null,
      queue: null,
      infrastructure: null,
    };

    const [docResult, queueResult, infraResult] = await Promise.allSettled([
      fetchJson<DocumentMetrics>(buildApiUrl('/v1/admin/documents')),
      fetchJson<QueueStatus>(buildApiUrl('/v1/admin/queue-status')),
      fetchJson<InfrastructureStatus>(buildApiUrl('/v1/admin/containers')),
    ]);

    if (docResult.status === 'fulfilled') {
      setDocuments(docResult.value);
    } else {
      newErrors.documents =
        docResult.reason instanceof Error ? docResult.reason.message : 'Failed to load documents';
    }

    if (queueResult.status === 'fulfilled') {
      setQueue(queueResult.value);
    } else {
      newErrors.queue =
        queueResult.reason instanceof Error
          ? queueResult.reason.message
          : 'Failed to load queue status';
    }

    if (infraResult.status === 'fulfilled') {
      setInfrastructure(infraResult.value);
    } else {
      newErrors.infrastructure =
        infraResult.reason instanceof Error
          ? infraResult.reason.message
          : 'Failed to load infrastructure';
    }

    setErrors(newErrors);
    setLastRefreshed(new Date());
    setLoading(false);
  }, []);

  const toggleAutoRefresh = useCallback(() => {
    setAutoRefresh((prev) => !prev);
  }, []);

  // Initial fetch + auto-refresh interval
  useEffect(() => {
    let cancelled = false;

    const doFetch = async () => {
      if (!cancelled) await refresh();
    };

    doFetch();

    if (autoRefresh) {
      intervalRef.current = setInterval(doFetch, REFRESH_INTERVAL_MS);
    }
    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoRefresh, refresh]);

  return {
    documents,
    queue,
    infrastructure,
    loading,
    errors,
    autoRefresh,
    lastRefreshed,
    refresh,
    toggleAutoRefresh,
  };
}
