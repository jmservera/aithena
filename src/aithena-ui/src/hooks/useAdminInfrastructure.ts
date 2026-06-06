import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, buildApiUrl } from '../api';

/* ── API response types ───────────────────────────────────────────────── */

export interface ServiceEndpoint {
  name: string;
  url?: string;
  admin_url?: string | null;
  status: string;
  type?: string;
  description?: string;
}

export interface InfrastructureInfo {
  services: ServiceEndpoint[];
  solr_admin_url?: string;
  rabbitmq_admin_url?: string;
  redis_admin_url?: string;
  connections?: Record<string, string>;
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

export function getServiceAdminUrl(
  data: InfrastructureInfo | null,
  serviceName: string,
  fallbackUrl: string
): string {
  const service = data?.services.find((item) => item.name === serviceName);
  return safeAdminUrl(service?.admin_url ?? service?.url, fallbackUrl);
}

export function buildSolrSecurityUrl(solrAdminUrl: string): string {
  const safeSolrAdminUrl = safeAdminUrl(solrAdminUrl, '/admin/solr/');
  const base = safeSolrAdminUrl.endsWith('/') ? safeSolrAdminUrl : `${safeSolrAdminUrl}/`;
  return `${base}ui/#/~security`;
}

export function safeAdminUrl(candidate: string | null | undefined, fallbackUrl: string): string {
  const value = candidate?.trim();
  if (!value) return fallbackUrl;

  if (hasUnsafeUrlCharacters(value) || typeof window === 'undefined') {
    return fallbackUrl;
  }

  try {
    const parsed = new URL(value, window.location.origin);
    if (
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      parsed.origin === window.location.origin
    ) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    // fall through to the safe fallback
  }

  return fallbackUrl;
}

export function redactUrlForDisplay(candidate: string | null | undefined): string {
  const value = candidate?.trim();
  if (!value) return '—';
  if (hasUnsafeUrlCharacters(value)) return '—';

  if (value.startsWith('/') && !value.startsWith('//')) {
    try {
      const parsed = new URL(value, 'http://localhost');
      return parsed.pathname;
    } catch {
      return '—';
    }
  }

  if (value.startsWith('//')) {
    try {
      const parsed = new URL(value, 'http://localhost');
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return '—';
      }
      parsed.username = '';
      parsed.password = '';
      parsed.search = '';
      parsed.hash = '';
      return `//${parsed.host}${parsed.pathname}`;
    } catch {
      return '—';
    }
  }

  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return '—';
    }
    parsed.username = '';
    parsed.password = '';
    parsed.search = '';
    parsed.hash = '';
    return parsed.toString();
  } catch {
    return value.includes('@') ? '—' : value;
  }
}

function hasUnsafeUrlCharacters(value: string): boolean {
  return [...value].some((char) => {
    const codePoint = char.codePointAt(0);
    return char === '\\' || codePoint === undefined || codePoint < 32 || codePoint === 127;
  });
}
