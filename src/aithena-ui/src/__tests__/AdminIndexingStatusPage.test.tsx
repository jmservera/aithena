import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import AdminIndexingStatusPage from '../pages/AdminIndexingStatusPage';
import { IntlWrapper } from './test-intl-wrapper';

const mockSummary = {
  total: 150,
  queued: 10,
  processing: 3,
  processed: 130,
  failed: 7,
  total_pages: 45000,
  total_chunks: 120000,
};

const mockDocuments = [
  {
    id: 'doc-queued-1',
    status: 'queued',
    path: '/data/documents/pending.pdf',
    title: 'Pending Book',
    text_indexed: false,
    embedding_indexed: false,
    page_count: 0,
    chunk_count: 0,
    error: null,
    error_stage: null,
    timestamp: '2024-01-15T10:00:00Z',
  },
  {
    id: 'doc-processing-1',
    status: 'processing',
    path: '/data/documents/in_progress.pdf',
    title: 'In Progress Book',
    text_indexed: true,
    embedding_indexed: false,
    page_count: 300,
    chunk_count: 0,
    error: null,
    error_stage: null,
    timestamp: '2024-01-15T09:00:00Z',
  },
  {
    id: 'doc-processed-1',
    status: 'processed',
    path: '/data/documents/done.pdf',
    title: 'Done Book',
    text_indexed: true,
    embedding_indexed: true,
    page_count: 200,
    chunk_count: 500,
    error: null,
    error_stage: null,
    timestamp: '2024-01-14T08:00:00Z',
  },
  {
    id: 'doc-failed-1',
    status: 'failed',
    path: '/data/documents/broken.pdf',
    title: 'Broken Book',
    text_indexed: false,
    embedding_indexed: false,
    page_count: 0,
    chunk_count: 0,
    error: 'Extraction failed: corrupt PDF',
    error_stage: 'text_extraction',
    timestamp: '2024-01-13T07:00:00Z',
  },
];

const populatedResponse = {
  summary: mockSummary,
  documents: mockDocuments,
};

const emptyResponse = {
  summary: {
    total: 0,
    queued: 0,
    processing: 0,
    processed: 0,
    failed: 0,
    total_pages: 0,
    total_chunks: 0,
  },
  documents: [],
};

function mockFetch(response: object, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

describe('AdminIndexingStatusPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('shows loading state initially', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
    expect(screen.getByText(/loading indexing status/i)).toBeInTheDocument();
  });

  it('renders all 7 metric cards when data loads', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    // Metric labels
    expect(screen.getByText('Total Files')).toBeInTheDocument();
    expect(screen.getByText('Pages Indexed')).toBeInTheDocument();
    expect(screen.getByText('Chunks Indexed')).toBeInTheDocument();

    // Check large metric values that are unique
    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('130')).toBeInTheDocument();
    expect(screen.getByText('45,000')).toBeInTheDocument();
    expect(screen.getByText('120,000')).toBeInTheDocument();

    // Verify the metrics section exists
    const metricsSection = screen.getByLabelText(/indexing summary metrics/i);
    expect(metricsSection).toBeInTheDocument();
    const metricCards = metricsSection.querySelectorAll('.admin-metric-card');
    expect(metricCards).toHaveLength(7);
  });

  it('renders currently processing section with progress indicators', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('Currently Processing')).toBeInTheDocument();
    });

    expect(screen.getAllByText('In Progress Book').length).toBeGreaterThanOrEqual(1);
    // Progress bars should be present
    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars.length).toBeGreaterThanOrEqual(2);
  });

  it('renders document table with all columns', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending.pdf')).toBeInTheDocument();
    });

    // Column headers
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Path')).toBeInTheDocument();
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Timestamp')).toBeInTheDocument();

    // Document paths
    expect(screen.getByText('/data/documents/in_progress.pdf')).toBeInTheDocument();
    expect(screen.getByText('/data/documents/done.pdf')).toBeInTheDocument();
    expect(screen.getByText('/data/documents/broken.pdf')).toBeInTheDocument();
  });

  it('shows error message from failed document', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText(/extraction failed/i)).toBeInTheDocument();
    });
  });

  it('filters documents by status when filter button is clicked', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending.pdf')).toBeInTheDocument();
    });

    // Click "Failed" filter
    const filterButtons = screen.getAllByRole('button', { name: /failed/i });
    const failedFilter = filterButtons.find((btn) => btn.getAttribute('aria-pressed') !== null);
    expect(failedFilter).toBeDefined();
    fireEvent.click(failedFilter!);

    // Should show only failed doc
    expect(screen.getByText('/data/documents/broken.pdf')).toBeInTheDocument();
    expect(screen.queryByText('/data/documents/pending.pdf')).not.toBeInTheDocument();
    expect(screen.queryByText('/data/documents/done.pdf')).not.toBeInTheDocument();
  });

  it('shows empty state when filter has no matching documents', async () => {
    const noFailedResponse = {
      summary: { ...mockSummary, failed: 0 },
      documents: mockDocuments.filter((d) => d.status !== 'failed'),
    };
    vi.stubGlobal('fetch', mockFetch(noFailedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('All Documents')).toBeInTheDocument();
    });

    // Click "Failed" filter
    const filterButtons = screen.getAllByRole('button', { name: /failed/i });
    const failedFilter = filterButtons.find((btn) => btn.getAttribute('aria-pressed') !== null);
    fireEvent.click(failedFilter!);

    expect(screen.getByText(/no documents match/i)).toBeInTheDocument();
  });

  it('shows error banner when API fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('renders refresh button', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  it('renders auto-refresh toggle', async () => {
    vi.stubGlobal('fetch', mockFetch(emptyResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('Indexing Status')).toBeInTheDocument();
    });

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();
  });

  it('auto-refresh calls API periodically when enabled', async () => {
    const fetchMock = mockFetch(populatedResponse);
    vi.stubGlobal('fetch', fetchMock);
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const initialCalls = fetchMock.mock.calls.length;

    // Enable auto-refresh
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    // Advance timer by 10 seconds
    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });

    // Should have made at least one additional call
    expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCalls);
  });

  it('does not show processing section when no documents are processing', async () => {
    const noProcResponse = {
      summary: { ...mockSummary, processing: 0 },
      documents: mockDocuments.filter((d) => d.status !== 'processing'),
    };
    vi.stubGlobal('fetch', mockFetch(noProcResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('All Documents')).toBeInTheDocument();
    });

    expect(screen.queryByText('Currently Processing')).not.toBeInTheDocument();
  });

  it('renders status badges in the table', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/pending.pdf')).toBeInTheDocument();
    });

    // Check for status badge elements
    const badges = document.querySelectorAll('.status-badge');
    expect(badges.length).toBeGreaterThanOrEqual(4);
  });

  it('renders boolean indicators for text_indexed and embedding_indexed', async () => {
    vi.stubGlobal('fetch', mockFetch(populatedResponse));
    render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

    await waitFor(() => {
      expect(screen.getByText('/data/documents/done.pdf')).toBeInTheDocument();
    });

    const yesIndicators = screen.getAllByLabelText('yes');
    const noIndicators = screen.getAllByLabelText('no');
    expect(yesIndicators.length).toBeGreaterThanOrEqual(1);
    expect(noIndicators.length).toBeGreaterThanOrEqual(1);
  });
});
