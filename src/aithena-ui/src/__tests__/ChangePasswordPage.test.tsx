import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ChangePasswordPage from '../pages/ChangePasswordPage';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';
import { IntlWrapper } from './test-intl-wrapper';

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: { id: 1, username: 'dallas', role: 'user' },
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
        <MemoryRouter initialEntries={['/profile/change-password']}>
          <Routes>
            <Route path="/profile/change-password" element={<ChangePasswordPage />} />
            <Route path="/profile" element={<div>Profile Page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </IntlWrapper>
  );
}

describe('ChangePasswordPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the change password form', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /change password/i })).toBeDisabled();
  });

  it('shows error when passwords do not match', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/current password/i), 'oldpassword1');
    await user.type(screen.getByLabelText(/^new password$/i), 'newpassword1');
    await user.type(screen.getByLabelText(/confirm new password/i), 'differentpwd1');
    await user.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    });
  });

  it('shows error when password is too short', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/current password/i), 'oldpass');
    await user.type(screen.getByLabelText(/^new password$/i), 'short');
    await user.type(screen.getByLabelText(/confirm new password/i), 'short');
    await user.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    });
  });

  it('calls change password API on valid submit', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Password changed' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/current password/i), 'oldpassword123');
    await user.type(screen.getByLabelText(/^new password$/i), 'newpassword123');
    await user.type(screen.getByLabelText(/confirm new password/i), 'newpassword123');
    await user.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/v1/auth/change-password'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({
            current_password: 'oldpassword123',
            new_password: 'newpassword123',
          }),
        })
      );
    });
  });

  it('shows success message after successful password change', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ message: 'ok' }),
      })
    );
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/current password/i), 'oldpassword123');
    await user.type(screen.getByLabelText(/^new password$/i), 'newpassword123');
    await user.type(screen.getByLabelText(/confirm new password/i), 'newpassword123');
    await user.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(screen.getByText(/password changed successfully/i)).toBeInTheDocument();
    });
  });

  it('shows backend error on API failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Current password is incorrect' }),
      })
    );
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/current password/i), 'wrongpassword');
    await user.type(screen.getByLabelText(/^new password$/i), 'newpassword123');
    await user.type(screen.getByLabelText(/confirm new password/i), 'newpassword123');
    await user.click(screen.getByRole('button', { name: /change password/i }));

    await waitFor(() => {
      expect(screen.getByText(/current password is incorrect/i)).toBeInTheDocument();
    });
  });

  it('has a back to profile link', () => {
    renderPage();
    const link = screen.getByRole('link', { name: /back to profile/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/profile');
  });
});
