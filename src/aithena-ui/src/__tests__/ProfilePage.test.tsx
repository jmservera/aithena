import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProfilePage from '../pages/ProfilePage';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';
import { IntlWrapper } from './test-intl-wrapper';

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: { id: 1, username: 'dallas', role: 'admin' },
    token: 'jwt-test',
    isAuthenticated: true,
    isLoading: false,
    error: null,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    clearError: vi.fn(),
    ...overrides,
  };
}

function renderPage(authValue?: AuthContextValue) {
  return render(
    <IntlWrapper>
      <AuthContext.Provider value={authValue ?? createAuthValue()}>
        <MemoryRouter initialEntries={['/profile']}>
          <Routes>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/profile/change-password" element={<div>Change Password Page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </IntlWrapper>
  );
}

describe('ProfilePage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the profile title', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /my profile/i })).toBeInTheDocument();
  });

  it('displays the username', () => {
    renderPage();
    expect(screen.getByText('dallas')).toBeInTheDocument();
  });

  it('displays the user role', () => {
    renderPage();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });

  it('renders a change password link', () => {
    renderPage();
    const link = screen.getByRole('link', { name: /change password/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/profile/change-password');
  });

  it('shows dashes when user info is missing', () => {
    renderPage(createAuthValue({ user: null }));
    expect(screen.getByRole('heading', { name: /my profile/i })).toBeInTheDocument();
  });
});
