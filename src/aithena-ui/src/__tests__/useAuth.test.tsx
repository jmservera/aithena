import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, AUTH_TOKEN_STORAGE_KEY } from '../api';
import { AuthProvider, useAuth } from '../contexts/AuthContext';

const loginResponse = {
  access_token: 'jwt-123',
  token_type: 'bearer',
  expires_in: 86400,
  user: {
    id: 1,
    username: 'dallas',
    role: 'admin',
  },
};

function mockJsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function AuthHarness() {
  const { error, isAuthenticated, isLoading, login, token, user } = useAuth();
  const [requestStatus, setRequestStatus] = useState<number | null>(null);

  return (
    <div>
      <div data-testid="auth-state">
        {isLoading ? 'loading' : isAuthenticated ? 'authenticated' : 'anonymous'}
      </div>
      <div data-testid="user-name">{user?.username ?? ''}</div>
      <div data-testid="token">{token ?? ''}</div>
      <div data-testid="auth-error">{error ?? ''}</div>
      <div data-testid="request-status">{requestStatus ?? ''}</div>
      <button
        type="button"
        onClick={() => {
          void login('dallas', 'secret').catch(() => undefined);
        }}
      >
        Login
      </button>
      <button
        type="button"
        onClick={() => {
          void apiFetch('/v1/stats/').then((response) => setRequestStatus(response.status));
        }}
      >
        Protected request
      </button>
    </div>
  );
}

function renderAuthHarness() {
  return render(
    <AuthProvider>
      <AuthHarness />
    </AuthProvider>
  );
}

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('logs in successfully and persists the token', async () => {
    // First call: cookie-based session recovery on mount (no session → 401)
    // Second call: actual login
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse({ detail: 'Not authenticated' }, 401))
      .mockResolvedValueOnce(mockJsonResponse(loginResponse));
    const user = userEvent.setup();

    renderAuthHarness();

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous');
    });

    await user.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated');
    });

    expect(screen.getByTestId('user-name')).toHaveTextContent('dallas');
    expect(screen.getByTestId('token')).toHaveTextContent('jwt-123');
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe('jwt-123');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/auth/login'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('surfaces login failures without persisting a token', async () => {
    // First call: cookie-based session recovery on mount (no session → 401)
    // Second call: login attempt that fails
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse({ detail: 'Not authenticated' }, 401))
      .mockResolvedValueOnce(mockJsonResponse({ detail: 'Invalid credentials' }, 401));
    const user = userEvent.setup();

    renderAuthHarness();

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous');
    });

    await user.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-error')).toHaveTextContent('Invalid credentials');
    });

    expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous');
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('restores the session from localStorage and validates it', async () => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'jwt-123');
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({ authenticated: true, user: loginResponse.user })
    );

    renderAuthHarness();

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated');
    });

    expect(screen.getByTestId('user-name')).toHaveTextContent('dallas');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/auth/validate'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('includes the stored token in Authorization headers for protected requests', async () => {
    // First call: cookie-based session recovery on mount (no session → 401)
    // Second call: login
    // Third call: protected API request
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse({ detail: 'Not authenticated' }, 401))
      .mockResolvedValueOnce(mockJsonResponse(loginResponse))
      .mockResolvedValueOnce(mockJsonResponse({ ok: true }, 200));
    const user = userEvent.setup();

    renderAuthHarness();

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous');
    });

    await user.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated');
    });

    await user.click(screen.getByRole('button', { name: 'Protected request' }));

    await waitFor(() => {
      expect(screen.getByTestId('request-status')).toHaveTextContent('200');
    });

    // The protected request is the third fetch call (index 2)
    const protectedRequest = vi.mocked(fetch).mock.calls[2]?.[1];
    expect(
      new Headers((protectedRequest as RequestInit | undefined)?.headers).get('Authorization')
    ).toBe('Bearer jwt-123');
  });

  it('auto-logs out after a 401 response from an API request', async () => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, 'jwt-123');
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse({ authenticated: true, user: loginResponse.user }))
      .mockResolvedValueOnce(mockJsonResponse({ detail: 'Expired session' }, 401));
    const user = userEvent.setup();

    renderAuthHarness();

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated');
    });

    await user.click(screen.getByRole('button', { name: 'Protected request' }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous');
    });

    expect(screen.getByTestId('request-status')).toHaveTextContent('401');
    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull();
  });
});
