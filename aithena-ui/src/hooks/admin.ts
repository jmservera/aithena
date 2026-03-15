import { useState, useCallback } from 'react';
import { buildApiUrl } from '../api';

const queueUrl = buildApiUrl('/v1/admin/queue');

export interface QueueDocument {
  id: string;
  path?: string;
  timestamp?: string;
  last_modified?: number;
  processed?: boolean;
  failed?: boolean;
  error?: string;
  title?: string;
  author?: string;
  year?: number;
  category?: string;
  page_count?: number;
}

export interface QueueState {
  total: number;
  queued: number;
  processed: number;
  failed: number;
  queued_documents: QueueDocument[];
  processed_documents: QueueDocument[];
  failed_documents: QueueDocument[];
}

export interface AdminState {
  data: QueueState | null;
  loading: boolean;
  error: string | null;
}

export interface UseAdminReturn extends AdminState {
  refresh: () => Promise<void>;
  requeueDocument: (id: string) => Promise<void>;
  requeueAllFailed: () => Promise<void>;
  clearProcessed: () => Promise<void>;
}

async function apiFetch(url: string, options?: RequestInit): Promise<unknown> {
  const response = await fetch(url, options);
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
  return response.json();
}

export function useAdmin(): UseAdminReturn {
  const [data, setData] = useState<QueueState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const json = (await apiFetch(queueUrl)) as QueueState;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load queue state');
    } finally {
      setLoading(false);
    }
  }, []);

  const requeueDocument = useCallback(
    async (id: string) => {
      await apiFetch(buildApiUrl(`/v1/admin/documents/${id}/requeue`), { method: 'POST' });
      await refresh();
    },
    [refresh]
  );

  const requeueAllFailed = useCallback(async () => {
    await apiFetch(buildApiUrl('/v1/admin/documents/requeue-failed'), { method: 'POST' });
    await refresh();
  }, [refresh]);

  const clearProcessed = useCallback(async () => {
    await apiFetch(buildApiUrl('/v1/admin/documents/processed'), { method: 'DELETE' });
    await refresh();
  }, [refresh]);

  return { data, loading, error, refresh, requeueDocument, requeueAllFailed, clearProcessed };
}
