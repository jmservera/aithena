import { useState, useCallback, useEffect } from 'react';
import { apiFetch, buildApiUrl } from '../api';

export type IndexingDocumentStatus = 'queued' | 'processing' | 'processed' | 'failed';

export interface IndexingDocument {
  id: string;
  status: IndexingDocumentStatus;
  path: string;
  title?: string;
  text_indexed: boolean;
  embedding_indexed: boolean;
  page_count: number;
  chunk_count: number;
  error?: string | null;
  error_stage?: string | null;
  timestamp?: string;
}

export interface IndexingSummary {
  total: number;
  queued: number;
  processing: number;
  processed: number;
  failed: number;
  total_pages: number;
  total_chunks: number;
}

export interface IndexingStatusResponse {
  summary: IndexingSummary;
  documents: IndexingDocument[];
}

export interface IndexingStatusState {
  data: IndexingStatusResponse | null;
  loading: boolean;
  error: string | null;
}

const AUTO_REFRESH_INTERVAL_MS = 10_000;

export interface UseAdminIndexingStatusReturn extends IndexingStatusState {
  refresh: () => Promise<void>;
  autoRefresh: boolean;
  setAutoRefresh: (enabled: boolean) => void;
  statusFilter: IndexingDocumentStatus | 'all';
  setStatusFilter: (filter: IndexingDocumentStatus | 'all') => void;
  page: number;
  setPage: (page: number) => void;
}

export function useAdminIndexingStatus(): UseAdminIndexingStatusReturn {
  const [data, setData] = useState<IndexingStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [statusFilter, setStatusFilterRaw] = useState<IndexingDocumentStatus | 'all'>('all');
  const [page, setPage] = useState(1);

  const setStatusFilter = useCallback((filter: IndexingDocumentStatus | 'all') => {
    setStatusFilterRaw(filter);
    setPage(1);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = buildApiUrl('/v1/admin/indexing-status');
      const response = await apiFetch(url);
      if (!response.ok) {
        let detail = `Request failed: ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) detail = String(body.detail);
        } catch {
          // ignore parse errors
        }
        throw new Error(detail);
      }
      const json = (await response.json()) as IndexingStatusResponse;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load indexing status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const id = setInterval(() => {
      refresh();
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => clearInterval(id);
  }, [autoRefresh, refresh]);

  return {
    data,
    loading,
    error,
    refresh,
    autoRefresh,
    setAutoRefresh,
    statusFilter,
    setStatusFilter,
    page,
    setPage,
  };
}
