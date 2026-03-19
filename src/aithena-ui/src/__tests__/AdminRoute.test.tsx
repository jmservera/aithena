import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AdminRoute from '../Components/AdminRoute';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';
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

function renderWithRoute(authValue: AuthContextValue) {
  return render(
    <IntlWrapper>
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={['/admin/users']}>
          <Routes>
            <Route element={<AdminRoute />}>
              <Route path="/admin/users" element={<div>User Management</div>} />
            </Route>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route path="/" element={<div>Home Page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </IntlWrapper>
  );
}

describe('AdminRoute', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders child route for admin users', () => {
    renderWithRoute(
      createAuthValue({
        isAuthenticated: true,
        user: { id: 1, username: 'admin', role: 'admin' },
        token: 'jwt-test',
      })
    );

    expect(screen.getByText('User Management')).toBeInTheDocument();
  });

  it('redirects non-admin users to home', () => {
    renderWithRoute(
      createAuthValue({
        isAuthenticated: true,
        user: { id: 2, username: 'reader', role: 'user' },
        token: 'jwt-test',
      })
    );

    expect(screen.getByText('Home Page')).toBeInTheDocument();
  });

  it('redirects unauthenticated users to login', () => {
    renderWithRoute(createAuthValue());

    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  it('shows loading state while auth is loading', () => {
    renderWithRoute(createAuthValue({ isLoading: true }));

    expect(screen.getByText(/restoring session/i)).toBeInTheDocument();
  });
});
