import { useState, useCallback } from 'react';
import { apiFetch, buildApiUrl } from '../api';

export interface UserRecord {
  id: number | string;
  username: string;
  role: string;
  created_at?: string;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role: string;
}

export interface UpdateUserPayload {
  username?: string;
  role?: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

async function apiRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(url, options);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = String(body.detail);
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

async function apiRequestNoBody(url: string, options?: RequestInit): Promise<void> {
  const response = await apiFetch(url, options);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = String(body.detail);
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }
}

export interface UseUsersReturn {
  users: UserRecord[];
  loading: boolean;
  error: string | null;
  fetchUsers: () => Promise<void>;
  createUser: (payload: CreateUserPayload) => Promise<void>;
  updateUser: (id: number | string, payload: UpdateUserPayload) => Promise<void>;
  deleteUser: (id: number | string) => Promise<void>;
}

export function useUsers(): UseUsersReturn {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<UserRecord[]>(buildApiUrl('/v1/auth/users'));
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  const createUser = useCallback(
    async (payload: CreateUserPayload) => {
      await apiRequest<UserRecord>(buildApiUrl('/v1/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await fetchUsers();
    },
    [fetchUsers]
  );

  const updateUser = useCallback(
    async (id: number | string, payload: UpdateUserPayload) => {
      await apiRequest<UserRecord>(buildApiUrl(`/v1/auth/users/${id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await fetchUsers();
    },
    [fetchUsers]
  );

  const deleteUser = useCallback(
    async (id: number | string) => {
      await apiRequestNoBody(buildApiUrl(`/v1/auth/users/${id}`), { method: 'DELETE' });
      await fetchUsers();
    },
    [fetchUsers]
  );

  return { users, loading, error, fetchUsers, createUser, updateUser, deleteUser };
}

export interface UseChangePasswordReturn {
  loading: boolean;
  error: string | null;
  success: boolean;
  changePassword: (payload: ChangePasswordPayload) => Promise<void>;
  reset: () => void;
}

export function useChangePassword(): UseChangePasswordReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const changePassword = useCallback(async (payload: ChangePasswordPayload) => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      await apiRequestNoBody(buildApiUrl('/v1/auth/change-password'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to change password');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setError(null);
    setSuccess(false);
  }, []);

  return { loading, error, success, changePassword, reset };
}
