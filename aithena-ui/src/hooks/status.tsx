import { useState, useEffect, useCallback } from "react";

const statusBaseURL = `${import.meta.env.VITE_API_URL}/v1/status/`;

export interface ServiceHealth {
  status: "ok" | "error" | "unknown";
  message?: string;
}

export interface FailedDocument {
  path: string;
  error: string;
  stage?: string;
}

export interface IndexingStats {
  discovered: number;
  indexed: number;
  failed: number;
  pending: number;
}

export interface StatusResponse {
  indexing: IndexingStats;
  services: {
    solr: ServiceHealth;
    redis: ServiceHealth;
    rabbitmq: ServiceHealth;
  };
  failed_documents: FailedDocument[];
}

export function useStatus() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(statusBaseURL);
      if (!response.ok) {
        throw new Error(`Status request failed: ${response.status}`);
      }
      const json: StatusResponse = await response.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return { data, loading, error };
}
