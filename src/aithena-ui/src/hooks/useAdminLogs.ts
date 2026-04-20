import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, buildApiUrl } from '../api';

/* ── Types ────────────────────────────────────────────────────────────── */

export interface ServiceInfo {
  name: string;
  status: string;
}

export interface AdminLogsState {
  services: ServiceInfo[];
  selectedService: string;
  tailLines: number;
  logLines: string[];
  loading: boolean;
  servicesLoading: boolean;
  error: string | null;
  servicesError: string | null;
  autoRefresh: boolean;
  refreshInterval: number;
  searchFilter: string;
}

export interface UseAdminLogsReturn extends AdminLogsState {
  setSelectedService: (service: string) => void;
  setTailLines: (n: number) => void;
  setAutoRefresh: (on: boolean) => void;
  setRefreshInterval: (ms: number) => void;
  setSearchFilter: (filter: string) => void;
  refresh: () => Promise<void>;
}

export const TAIL_OPTIONS = [50, 100, 200, 500, 1000] as const;
export const INTERVAL_OPTIONS = [
  { value: 10_000, label: '10s' },
  { value: 30_000, label: '30s' },
  { value: 60_000, label: '60s' },
] as const;

/* ── Hook ─────────────────────────────────────────────────────────────── */

export function useAdminLogs(): UseAdminLogsReturn {
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [selectedService, setSelectedService] = useState('');
  const [tailLines, setTailLines] = useState(100);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [servicesLoading, setServicesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [servicesError, setServicesError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(30_000);
  const [searchFilter, setSearchFilter] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!selectedService) return;
    setLoading(true);
    setError(null);
    try {
      const url = buildApiUrl(
        `/v1/admin/logs/${encodeURIComponent(selectedService)}?tail=${tailLines}`
      );
      const response = await apiFetch(url);
      if (!response.ok) {
        let detail = `Request failed: ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) detail = String(body.detail);
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      const raw = await response.text();
      setLogLines(raw.split('\n'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
      setLogLines([]);
    } finally {
      setLoading(false);
    }
  }, [selectedService, tailLines]);

  // Fetch services on mount
  useEffect(() => {
    let cancelled = false;

    const doFetch = async () => {
      setServicesLoading(true);
      setServicesError(null);
      try {
        const url = buildApiUrl('/v1/admin/containers');
        const response = await apiFetch(url);
        if (!response.ok) {
          let detail = `Request failed: ${response.status}`;
          try {
            const body = await response.json();
            if (body?.detail) detail = String(body.detail);
          } catch {
            // ignore
          }
          throw new Error(detail);
        }
        const data = await response.json();
        if (!cancelled) {
          setServices(data.containers ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setServicesError(err instanceof Error ? err.message : 'Failed to load services');
          setServices([]);
        }
      } finally {
        if (!cancelled) {
          setServicesLoading(false);
        }
      }
    };

    doFetch();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch logs when service or tail changes
  useEffect(() => {
    let cancelled = false;

    const doFetch = async () => {
      if (!cancelled) await refresh();
    };

    if (selectedService) {
      doFetch();
    }
    return () => {
      cancelled = true;
    };
  }, [selectedService, tailLines, refresh]);

  // Auto-refresh interval
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (autoRefresh && selectedService) {
      intervalRef.current = setInterval(() => {
        refresh();
      }, refreshInterval);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoRefresh, refreshInterval, selectedService, refresh]);

  return {
    services,
    selectedService,
    tailLines,
    logLines,
    loading,
    servicesLoading,
    error,
    servicesError,
    autoRefresh,
    refreshInterval,
    searchFilter,
    setSelectedService,
    setTailLines,
    setAutoRefresh,
    setRefreshInterval,
    setSearchFilter,
    refresh,
  };
}
