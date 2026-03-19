import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import UserManagementPage from '../pages/UserManagementPage';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';
import { IntlWrapper } from './test-intl-wrapper';

const adminUser = { id: 1, username: 'admin', role: 'admin' };

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: adminUser,
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

const usersListResponse = [
  { id: 1, username: 'admin', role: 'admin', created_at: '2024-01-01T00:00:00' },
  { id: 2, username: 'reader', role: 'user', created_at: '2024-02-15T10:00:00' },
];

function mockFetch(response: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

function renderPage(authValue?: AuthContextValue) {
  return render(
    <IntlWrapper>
      <AuthContext.Provider value={authValue ?? createAuthValue()}>
        <MemoryRouter initialEntries={['/admin/users']}>
          <Routes>
            <Route path="/admin/users" element={<UserManagementPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </IntlWrapper>
  );
}

describe('UserManagementPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the user list after loading', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('reader')).toBeInTheDocument();
    });

    expect(screen.getByText(/User Management/i)).toBeInTheDocument();
    const adminCells = screen.getAllByText('admin');
    expect(adminCells.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the Add User button', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add user/i })).toBeInTheDocument();
    });
  });

  it('opens and closes the add user modal', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add user/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /add user/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens the edit user modal when edit is clicked', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('reader')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByRole('button', { name: /^edit$/i });
    await user.click(editButtons[1]); // Edit "reader"

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText(/^username$/i)).toHaveValue('reader');
  });

  it('opens the delete confirmation modal', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('reader')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole('button', { name: /^delete$/i });
    const enabledDelete = deleteButtons.find((btn) => !btn.hasAttribute('disabled'));
    expect(enabledDelete).toBeDefined();
    await user.click(enabledDelete!);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
  });

  it('shows error banner when fetching users fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('shows empty state when no users', async () => {
    vi.stubGlobal('fetch', mockFetch([]));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no users found/i)).toBeInTheDocument();
    });
  });

  it('disables delete button for current user', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('reader')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole('button', { name: /^delete$/i });
    expect(deleteButtons[0]).toBeDisabled();
    expect(deleteButtons[1]).not.toBeDisabled();
  });

  it('shows validation error for password mismatch in add modal', async () => {
    vi.stubGlobal('fetch', mockFetch(usersListResponse));
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add user/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /add user/i }));
    await user.type(screen.getByLabelText(/^username$/i), 'newuser');
    await user.type(screen.getByLabelText(/^password$/i), 'longpassword1');
    await user.type(screen.getByLabelText(/confirm password/i), 'differentpwd1');

    fireEvent.submit(screen.getByRole('dialog').querySelector('form')!);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });
});
