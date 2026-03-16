import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
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

function renderLoginPage(
  authValue: AuthContextValue,
  initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries'] = ['/login']
) {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/search" element={<div>Search page</div>} />
          <Route path="/admin" element={<div>Admin page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe('LoginPage', () => {
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
        <AuthContext.Provider value={authValue}>
          <MemoryRouter initialEntries={['/login']}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/search" element={<div>Search page</div>} />
            </Routes>
          </MemoryRouter>
        </AuthContext.Provider>
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
