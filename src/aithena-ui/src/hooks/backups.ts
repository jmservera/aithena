import { useState, useCallback, useEffect } from 'react';
import { apiFetch, buildApiUrl } from '../api';

export type BackupTier = 'critical' | 'high' | 'medium' | 'all';
export type BackupStatus = 'completed' | 'in_progress' | 'failed' | 'pending';

export interface BackupComponent {
  name: string;
  size: number;
  status: BackupStatus;
}

export interface BackupEntry {
  id: string;
  timestamp: string;
  tier: BackupTier;
  status: BackupStatus;
  size: number;
  components: BackupComponent[];
  duration_seconds?: number;
  error?: string;
}

export interface TierStatus {
  tier: BackupTier;
  last_backup: string | null;
  age_hours: number;
  rpo_hours: number;
  size: number;
  status: BackupStatus;
}

export interface BackupListResponse {
  backups: BackupEntry[];
  total: number;
}

export interface BackupStatusResponse {
  tiers: TierStatus[];
}

export interface RestoreRequest {
  backup_id: string;
  components?: string[];
}

export interface RestoreResult {
  status: 'completed' | 'failed';
  message: string;
  components_restored: string[];
  duration_seconds: number;
}

export type RestoreWizardStep = 'select' | 'preview' | 'confirm' | 'progress';

async function apiRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(url, options);
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
  return (await response.json()) as T;
}

export interface UseBackupsReturn {
  backups: BackupEntry[];
  tierStatuses: TierStatus[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  triggerBackup: (tier: BackupTier) => Promise<void>;
  triggerRestore: (request: RestoreRequest) => Promise<RestoreResult>;
  testRestore: (request: RestoreRequest) => Promise<RestoreResult>;
}

export function useBackups(): UseBackupsReturn {
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [tierStatuses, setTierStatuses] = useState<TierStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBackups = useCallback(async () => {
    const data = await apiRequest<BackupListResponse>(buildApiUrl('/v1/admin/backups'));
    setBackups(data.backups);
  }, []);

  const fetchTierStatus = useCallback(async () => {
    const data = await apiRequest<BackupStatusResponse>(buildApiUrl('/v1/admin/backups/status'));
    setTierStatuses(data.tiers);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([fetchBackups(), fetchTierStatus()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load backup data');
    } finally {
      setLoading(false);
    }
  }, [fetchBackups, fetchTierStatus]);

  useEffect(() => {
    let cancelled = false;
    async function loadInitial() {
      setLoading(true);
      setError(null);
      try {
        const [backupsData, statusData] = await Promise.all([
          apiRequest<BackupListResponse>(buildApiUrl('/v1/admin/backups')),
          apiRequest<BackupStatusResponse>(buildApiUrl('/v1/admin/backups/status')),
        ]);
        if (!cancelled) {
          setBackups(backupsData.backups);
          setTierStatuses(statusData.tiers);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load backup data');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const triggerBackup = useCallback(
    async (tier: BackupTier) => {
      await apiRequest(buildApiUrl('/v1/admin/backups'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier }),
      });
      await refresh();
    },
    [refresh]
  );

  const triggerRestore = useCallback(
    async (request: RestoreRequest): Promise<RestoreResult> => {
      const result = await apiRequest<RestoreResult>(buildApiUrl('/v1/admin/restore'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      await refresh();
      return result;
    },
    [refresh]
  );

  const testRestore = useCallback(async (request: RestoreRequest): Promise<RestoreResult> => {
    return apiRequest<RestoreResult>(buildApiUrl('/v1/admin/restore/test'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }, []);

  return { backups, tierStatuses, loading, error, refresh, triggerBackup, triggerRestore, testRestore };
}

export function tierHealthColor(tier: TierStatus): 'green' | 'yellow' | 'red' {
  if (tier.status === 'failed') return 'red';
  if (!tier.last_backup) return 'red';
  if (tier.age_hours > tier.rpo_hours) return 'red';
  if (tier.age_hours > tier.rpo_hours * 0.8) return 'yellow';
  return 'green';
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}
