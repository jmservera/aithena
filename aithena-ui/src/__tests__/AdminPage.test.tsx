import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import AdminPage from '../pages/AdminPage';

const emptyQueueResponse = {
  total: 0,
  queued: 0,
  processed: 0,
  failed: 0,
  queued_documents: [],
  processed_documents: [],
  failed_documents: [],
};

const populatedQueueResponse = {
  total: 3,
  queued: 1,
  processed: 1,
  failed: 1,
  queued_documents: [
    {
      id: 'cXVldWVkLWtleQ==',
      path: '/data/documents/pending_book.pdf',
      timestamp: '2024-01-15T10:00:00',
    },
  ],
  processed_documents: [
    {
      id: 'cHJvY2Vzc2VkLWtleQ==',
      path: '/data/documents/indexed_book.pdf',
      title: 'Indexed Book',
      author: 'Jane Doe',
      year: 2023,
      timestamp: '2024-01-14T09:00:00',
    },
  ],
  failed_documents: [
    {
      id: 'ZmFpbGVkLWtleQ==',
      path: '/data/documents/broken_book.pdf',
      error: 'Extraction failed: corrupt PDF',
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

describe('AdminPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading state initially', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})) // never resolves
    );
    render(<AdminPage />);
    expect(screen.getByText(/loading queue state/i)).toBeInTheDocument();
  });

  it('renders metrics and tabs when queue data loads', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText('🏛️ Admin Dashboard')).toBeInTheDocument();
    });

    // Metrics cards should be present
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.getByText('Processed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('shows empty state for queued tab when no documents', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText(/no documents currently queued/i)).toBeInTheDocument();
    });
  });

  it('renders queued documents in the queued tab', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending_book.pdf')).toBeInTheDocument();
    });
  });

  it('switches to the processed tab and shows processed documents', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /processed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /processed/i }));
    expect(screen.getByText('/data/documents/indexed_book.pdf')).toBeInTheDocument();
    expect(screen.getByText('Indexed Book')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
  });

  it('switches to the failed tab and shows failed documents with requeue button', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    expect(screen.getByText('/data/documents/broken_book.pdf')).toBeInTheDocument();
    expect(screen.getByText(/extraction failed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /🔄 Requeue$/i })).toBeInTheDocument();
  });

  it('shows error banner when API call fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('shows failed empty state when no failed documents', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /failed/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /failed/i }));
    expect(screen.getByText(/no failed documents/i)).toBeInTheDocument();
  });

  it('renders a Refresh button', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyQueueResponse));
    render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  it('does not render an iframe', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyQueueResponse));
    const { container } = render(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText('🏛️ Admin Dashboard')).toBeInTheDocument();
    });

    expect(container.querySelector('iframe')).toBeNull();
  });
});
