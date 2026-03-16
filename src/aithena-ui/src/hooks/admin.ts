import { useState, useCallback } from 'react';
import { apiFetch, buildApiUrl } from '../api';

// GET /v1/admin/documents — canonical API contract from the admin operations API
const documentsUrl = buildApiUrl('/v1/admin/documents');

export type DocumentStatus = 'queued' | 'processed' | 'failed';

export interface AdminDocument {
  id: string;
  status: DocumentStatus;
  path?: string;
  timestamp?: string;
  last_modified?: number;
  error?: string;
  title?: string;
  author?: string;
  year?: number;
  category?: string;
  page_count?: number;
}

export interface AdminDocumentsResponse {
  total: number;
  queued: number;
  processed: number;
  failed: number;
  documents: AdminDocument[];
}

export interface QueueState {
  total: number;
  queued: number;
  processed: number;
  failed: number;
  /** All documents; filter client-side by doc.status */
  documents: AdminDocument[];
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

async function apiRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(url, options);
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

export function useAdmin(): UseAdminReturn {
  const [data, setData] = useState<QueueState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const json = await apiRequest<AdminDocumentsResponse>(documentsUrl);
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load queue state');
    } finally {
      setLoading(false);
    }
  }, []);

  const requeueDocument = useCallback(
    async (id: string) => {
      await apiRequest(buildApiUrl(`/v1/admin/documents/${id}/requeue`), { method: 'POST' });
      await refresh();
    },
    [refresh]
  );

  const requeueAllFailed = useCallback(async () => {
    await apiRequest(buildApiUrl('/v1/admin/documents/requeue-failed'), { method: 'POST' });
    await refresh();
  }, [refresh]);

  const clearProcessed = useCallback(async () => {
    await apiRequest(buildApiUrl('/v1/admin/documents/processed'), { method: 'DELETE' });
    await refresh();
  }, [refresh]);

  return { data, loading, error, refresh, requeueDocument, requeueAllFailed, clearProcessed };
}
