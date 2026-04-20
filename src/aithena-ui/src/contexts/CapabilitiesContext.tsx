/**
 * CapabilitiesContext — fetch and cache backend search capabilities.
 *
 * Calls GET /v1/capabilities at startup and exposes the result to the
 * component tree.  Components use `useCapabilities()` to read:
 * - which search modes are available
 * - the search architecture (hnsw vs hybrid-rerank)
 * - whether similar books is available
 *
 * If the endpoint is unavailable, assumes HNSW with all modes (graceful fallback).
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { apiFetch, buildApiUrl } from '../api';
import type { SearchMode } from '../hooks/search';

export interface Capabilities {
  searchModes: SearchMode[];
  architecture: string;
  vectorDimensions: number;
  similarBooks: boolean;
  loading: boolean;
}

const DEFAULT_CAPABILITIES: Capabilities = {
  searchModes: ['keyword', 'semantic', 'hybrid'],
  architecture: 'hnsw',
  vectorDimensions: 768,
  similarBooks: true,
  loading: true,
};

const CapabilitiesContext = createContext<Capabilities>(DEFAULT_CAPABILITIES);

export function CapabilitiesProvider({ children }: { children: ReactNode }) {
  const [caps, setCaps] = useState<Capabilities>(DEFAULT_CAPABILITIES);

  useEffect(() => {
    let cancelled = false;

    async function fetchCapabilities() {
      try {
        const resp = await apiFetch(buildApiUrl('/v1/capabilities'), {
          skipAuth: true,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (!cancelled) {
          setCaps({
            searchModes: data.search_modes ?? ['keyword', 'semantic', 'hybrid'],
            architecture: data.architecture ?? 'hnsw',
            vectorDimensions: data.vector_dimensions ?? 768,
            similarBooks: data.similar_books ?? true,
            loading: false,
          });
        }
      } catch {
        // Graceful fallback: assume HNSW with all modes
        if (!cancelled) {
          setCaps({ ...DEFAULT_CAPABILITIES, loading: false });
        }
      }
    }

    fetchCapabilities();
    return () => {
      cancelled = true;
    };
  }, []);

  return <CapabilitiesContext.Provider value={caps}>{children}</CapabilitiesContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCapabilities(): Capabilities {
  return useContext(CapabilitiesContext);
}
