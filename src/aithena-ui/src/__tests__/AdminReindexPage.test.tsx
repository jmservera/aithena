import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach } from 'vitest';
import AdminReindexPage from '../pages/AdminReindexPage';
import { IntlWrapper } from './test-intl-wrapper';

const successResponse = {
  message: 'Reindex triggered successfully',
  collection: 'books',
  solr: 'cleared',
  redis_cleared: 42,
};

function mockFetch(response: object, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

function mockFetchError(detail: string, status = 500) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: async () => ({ detail }),
  });
}

describe('AdminReindexPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the page title and description', () => {
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    expect(screen.getByText('Reindex Library')).toBeInTheDocument();
    expect(screen.getByText(/trigger a full reindex of the book library/i)).toBeInTheDocument();
  });

  it('renders the four reindex steps', () => {
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    expect(screen.getByText(/deleted from the Solr/i)).toBeInTheDocument();
    expect(screen.getByText(/Redis tracking state is cleared/i)).toBeInTheDocument();
    expect(screen.getByText(/document-lister automatically rediscovers/i)).toBeInTheDocument();
    expect(screen.getByText(/document-indexer re-embeds/i)).toBeInTheDocument();
  });

  it('renders warning about search unavailability', () => {
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    expect(screen.getByText(/Search will be unavailable/i)).toBeInTheDocument();
  });

  it('renders reindex button', () => {
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    const button = screen.getByRole('button', { name: /start full reindex/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('opens confirm dialog when button is clicked', async () => {
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));

    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByText('Confirm Full Reindex')).toBeInTheDocument();
    expect(screen.getByText(/delete all indexed documents/i)).toBeInTheDocument();
  });

  it('closes confirm dialog when cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('triggers reindex and shows success result', async () => {
    vi.stubGlobal('fetch', mockFetch(successResponse));
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

    await waitFor(() => {
      expect(screen.getByText(/✅ Reindex triggered successfully!/)).toBeInTheDocument();
    });

    expect(screen.getByText(/Solr collection: books/)).toBeInTheDocument();
    expect(screen.getByText(/Redis entries cleared: 42/)).toBeInTheDocument();
  });

  it('shows error message on reindex failure', async () => {
    vi.stubGlobal('fetch', mockFetchError('Solr connection refused'));
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

    await waitFor(() => {
      expect(screen.getByText(/Solr connection refused/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('disables button during reindex', async () => {
    // Use a fetch that never resolves to keep loading state
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

    await waitFor(() => {
      const button = screen.getByRole('button', { name: /reindexing/i });
      expect(button).toBeDisabled();
    });
  });

  it('shows spinner text during reindex', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

    await waitFor(() => {
      expect(screen.getByText(/reindexing in progress/i)).toBeInTheDocument();
    });
  });

  it('has accessible description section', () => {
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    expect(screen.getByLabelText(/reindex process description/i)).toBeInTheDocument();
  });

  it('clears previous result when starting a new reindex', async () => {
    vi.stubGlobal('fetch', mockFetch(successResponse));
    const user = userEvent.setup();
    render(<AdminReindexPage />, { wrapper: IntlWrapper });

    // First reindex
    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

    await waitFor(() => {
      expect(screen.getByText(/✅ Reindex triggered successfully!/)).toBeInTheDocument();
    });

    // Click again — dialog should open and old result should clear
    await user.click(screen.getByRole('button', { name: /start full reindex/i }));
    expect(screen.queryByText(/✅ Reindex triggered successfully!/)).not.toBeInTheDocument();
  });
});
