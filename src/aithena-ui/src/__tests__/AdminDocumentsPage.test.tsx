import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import AdminDocumentsPage from '../pages/AdminDocumentsPage';
import { IntlWrapper } from './test-intl-wrapper';

const emptyResponse = {
  total: 0,
  queued: 0,
  processed: 0,
  failed: 0,
  documents: [],
};

const populatedResponse = {
  total: 5,
  queued: 2,
  processed: 2,
  failed: 1,
  documents: [
    {
      id: 'q1',
      status: 'queued',
      path: '/data/documents/pending_book.pdf',
      timestamp: '2024-01-15T10:00:00',
    },
    {
      id: 'q2',
      status: 'queued',
      path: '/data/documents/another_pending.pdf',
      timestamp: '2024-01-15T11:00:00',
    },
    {
      id: 'p1',
      status: 'processed',
      path: '/data/documents/indexed_book.pdf',
      title: 'Indexed Book',
      author: 'Jane Doe',
      year: 2023,
      page_count: 120,
      chunk_count: 45,
      timestamp: '2024-01-14T09:00:00',
    },
    {
      id: 'p2',
      status: 'processed',
      path: '/data/documents/second_book.pdf',
      title: 'Second Book',
      author: 'John Smith',
      year: 2022,
      page_count: 80,
      chunk_count: 30,
      timestamp: '2024-01-14T10:00:00',
    },
    {
      id: 'f1',
      status: 'failed',
      path: '/data/documents/broken_book.pdf',
      error:
        'Extraction failed: corrupt PDF header detected at byte offset 0x1F00 in document stream parser',
      timestamp: '2024-01-13T08:00:00',
    },
  ],
};

function mockFetch(response: object, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

describe('AdminDocumentsPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading state initially', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });
    expect(screen.getByText(/loading queue state/i)).toBeInTheDocument();
  });

  it('renders title and metrics when data loads', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('📄 Document Manager')).toBeInTheDocument();
    });

    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.getByText('Processed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('shows search input', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/filter by path/i)).toBeInTheDocument();
    });
  });

  it('renders queued documents in the queued tab', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending_book.pdf')).toBeInTheDocument();
    });
    expect(screen.getByText('/data/documents/another_pending.pdf')).toBeInTheDocument();
  });

  it('switches to processed tab and shows page_count and chunk_count', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /processed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /processed/i }));
    expect(screen.getByText('Indexed Book')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('45')).toBeInTheDocument();
    expect(screen.getByText('Pages')).toBeInTheDocument();
    expect(screen.getByText('Chunks')).toBeInTheDocument();
  });

  it('shows clear all with confirmation on processed tab', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /processed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /processed/i }));
    const clearBtn = screen.getByRole('button', { name: /clear all/i });
    expect(clearBtn).toBeInTheDocument();

    fireEvent.click(clearBtn);
    expect(screen.getByText(/clear.*processed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('switches to failed tab and shows requeue and delete buttons', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    expect(screen.getByText('/data/documents/broken_book.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /🔄 Requeue$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete.*broken_book/i })).toBeInTheDocument();
  });

  it('shows requeue all with confirmation on failed tab', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    const requeueAllBtn = screen.getByRole('button', { name: /requeue all/i });
    expect(requeueAllBtn).toBeInTheDocument();

    fireEvent.click(requeueAllBtn);
    expect(screen.getByText(/requeue.*failed/i)).toBeInTheDocument();
  });

  it('expands error details when clicking error text', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    const errorToggle = screen.getByRole('button', { name: /extraction failed/i });
    expect(errorToggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(errorToggle);
    expect(errorToggle).toHaveAttribute('aria-expanded', 'true');
    // The expanded detail region contains the full error text
    const detail = screen.getByRole('region', { name: /error details/i });
    expect(detail).toBeInTheDocument();
    expect(detail.textContent).toMatch(/document stream parser/i);
  });

  it('filters documents by path when typing in search', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending_book.pdf')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/filter by path/i);
    fireEvent.change(searchInput, { target: { value: 'pending_book' } });

    expect(screen.getByText('/data/documents/pending_book.pdf')).toBeInTheDocument();
    expect(screen.queryByText('/data/documents/another_pending.pdf')).not.toBeInTheDocument();
  });

  it('shows empty state for queued tab when no documents', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText(/no documents currently queued/i)).toBeInTheDocument();
    });
  });

  it('shows error banner when API call fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('renders a Refresh button', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  it('has accessible tab navigation with keyboard', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tablist')).toBeInTheDocument();
    });

    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(3);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(tabs[1]).toHaveAttribute('aria-selected', 'false');
  });

  it('calls delete when delete button is clicked', async () => {
    const fetchMock = mockFetch(populatedResponse);
    vi.stubGlobal('fetch', fetchMock);
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const deleteCall = calls.find((call: unknown[]) => {
        const opts = call[1] as Record<string, unknown> | undefined;
        return opts && opts.method === 'DELETE';
      });
      expect(deleteCall).toBeTruthy();
    });
  });

  it('shows empty states for all tabs', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyResponse));
    render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText(/no documents currently queued/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /processed/i }));
    expect(screen.getByText(/no processed documents/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    expect(screen.getByText(/no failed documents/i)).toBeInTheDocument();
  });
});
