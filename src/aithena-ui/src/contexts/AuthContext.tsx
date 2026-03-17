import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  apiFetch,
  AuthSession,
  AuthUser,
  clearStoredToken,
  getStoredToken,
  registerAuthFailureHandler,
  storeToken,
} from '../api';

interface AuthValidateResponse {
  authenticated: boolean;
  user?: AuthUser | null;
}

export interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

// Context + Provider colocated intentionally; fast refresh works on the Provider component.
// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function getErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') {
      return body.detail;
    }
    if (typeof body?.message === 'string') {
      return body.message;
    }
  } catch {
    // Ignore JSON parse failures.
  }

  return fallback;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(getStoredToken()));

  const clearAuthState = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setError(null);
    setIsLoading(false);
  }, []);

  useEffect(() => registerAuthFailureHandler(clearAuthState), [clearAuthState]);

  useEffect(() => {
    const storedToken = getStoredToken();
    if (!storedToken) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    async function validateSession() {
      try {
        const response = await apiFetch('/v1/auth/validate', {
          method: 'GET',
          skipUnauthorizedHandler: true,
        });

        if (!response.ok) {
          if (!cancelled) {
            clearAuthState();
          }
          return;
        }

        const data = (await response.json()) as AuthValidateResponse;
        if (!cancelled && data.authenticated && data.user) {
          setToken(storedToken);
          setUser(data.user);
          setError(null);
        } else if (!cancelled) {
          clearAuthState();
        }
      } catch (err) {
        if (!cancelled) {
          clearAuthState();
          setError(err instanceof Error ? err.message : 'Failed to validate session');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void validateSession();

    return () => {
      cancelled = true;
    };
  }, [clearAuthState]);

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiFetch('/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        skipAuth: true,
        skipUnauthorizedHandler: true,
      });

      if (!response.ok) {
        throw new Error(
          await getErrorMessage(response, 'Login failed. Check your username and password.')
        );
      }

      const data = (await response.json()) as AuthSession;
      storeToken(data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } catch (err) {
      clearStoredToken();
      setToken(null);
      setUser(null);
      const nextError = err instanceof Error ? err.message : 'Login failed';
      setError(nextError);
      throw err instanceof Error ? err : new Error(nextError);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);

    try {
      await apiFetch('/v1/auth/logout', {
        method: 'POST',
        skipUnauthorizedHandler: true,
      });
    } catch {
      // Clear local session state even if the backend logout call fails.
    } finally {
      clearAuthState();
    }
  }, [clearAuthState]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      isLoading,
      error,
      login,
      logout,
      clearError,
    }),
    [clearError, error, isLoading, login, logout, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
