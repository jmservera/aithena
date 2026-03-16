import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import ProtectedRoute from '../Components/ProtectedRoute';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';

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

function renderProtectedRoute(authValue: AuthContextValue) {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/admin" element={<div>Admin dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe('ProtectedRoute', () => {
  it('redirects anonymous users to the login page', () => {
    renderProtectedRoute(createAuthValue());

    expect(screen.getByText('Login page')).toBeInTheDocument();
  });

  it('renders protected content for authenticated users', () => {
    renderProtectedRoute(
      createAuthValue({
        user: { id: 1, username: 'dallas', role: 'admin' },
        token: 'jwt-123',
        isAuthenticated: true,
      })
    );

    expect(screen.getByText('Admin dashboard')).toBeInTheDocument();
  });

  it('shows a session restore placeholder while auth is loading', () => {
    renderProtectedRoute(createAuthValue({ isLoading: true }));

    expect(screen.getByText(/restoring session/i)).toBeInTheDocument();
    expect(screen.queryByText('Login page')).not.toBeInTheDocument();
  });
});
