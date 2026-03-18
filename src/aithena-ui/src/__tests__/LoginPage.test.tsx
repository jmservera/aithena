import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AUTH_TOKEN_STORAGE_KEY } from '../api';
import LoginPage from '../pages/LoginPage';
import { AuthContext, AuthContextValue, AuthProvider } from '../contexts/AuthContext';
import { IntlWrapper } from './test-intl-wrapper';

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    clearError: vi.fn(),
    ...overrides,
  };
}

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

function renderLoginPage(
  authValue: AuthContextValue,
  initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries'] = ['/login']
) {
  return render(
    <IntlWrapper>
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/search" element={<div>Search page</div>} />
            <Route path="/admin" element={<div>Admin page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </IntlWrapper>
  );
}

function renderLoginPageWithProvider(
  initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries'] = ['/login']
) {
  return render(
    <IntlWrapper>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/search" element={<div>Search page</div>} />
            <Route path="/admin" element={<div>Admin page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </IntlWrapper>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  it('renders the login form', () => {
    renderLoginPage(createAuthValue());

    expect(screen.getByRole('heading', { name: /sign in to aithena/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled();
  });

  it('submits credentials and navigates after a successful login', async () => {
    const submittedCredentials: Array<[string, string]> = [];
    const user = userEvent.setup();

    function StatefulLoginPage() {
      const [isAuthenticated, setIsAuthenticated] = useState(false);

      const authValue = createAuthValue({
        isAuthenticated,
        token: isAuthenticated ? 'jwt-123' : null,
        user: isAuthenticated ? { id: 1, username: 'dallas', role: 'admin' } : null,
        login: vi.fn().mockImplementation(async (username: string, password: string) => {
          submittedCredentials.push([username, password]);
          setIsAuthenticated(true);
        }),
      });

      return (
        <IntlWrapper>
          <AuthContext.Provider value={authValue}>
            <MemoryRouter initialEntries={['/login']}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/search" element={<div>Search page</div>} />
              </Routes>
            </MemoryRouter>
          </AuthContext.Provider>
        </IntlWrapper>
      );
    }

    render(<StatefulLoginPage />);

    await user.type(screen.getByLabelText(/username/i), 'dallas');
    await user.type(screen.getByLabelText(/password/i), 'secret');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(submittedCredentials).toEqual([['dallas', 'secret']]);
      expect(screen.getByText('Search page')).toBeInTheDocument();
    });
  });

  it('stores the token when the login form succeeds through the auth provider', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(mockJsonResponse(loginResponse));
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    renderLoginPageWithProvider();

    await user.type(screen.getByLabelText(/username/i), 'dallas');
    await user.type(screen.getByLabelText(/password/i), 'secret');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Search page')).toBeInTheDocument();
    });

    expect(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe('jwt-123');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/auth/login'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'dallas', password: 'secret' }),
      })
    );
  });

  it('redirects authenticated users to the original destination', async () => {
    renderLoginPage(
      createAuthValue({
        isAuthenticated: true,
        user: { id: 1, username: 'dallas', role: 'admin' },
        token: 'jwt-123',
      }),
      [{ pathname: '/login', state: { from: { pathname: '/admin' } } }]
    );

    await waitFor(() => {
      expect(screen.getByText('Admin page')).toBeInTheDocument();
    });
  });

  it('shows the auth error message when login fails', () => {
    renderLoginPage(createAuthValue({ error: 'Invalid credentials' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials');
  });
});
