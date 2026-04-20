import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import AdminSystemStatusPage from '../pages/AdminSystemStatusPage';
import { IntlWrapper } from './test-intl-wrapper';

/* ── Mock data ────────────────────────────────────────────────────────── */

const mockContainersResponse = {
  containers: [
    {
      name: 'solr-search',
      status: 'up',
      type: 'service',
      version: '1.2.0',
      commit: 'abc1234def5678',
    },
    {
      name: 'embeddings-server',
      status: 'up',
      type: 'service',
      version: '1.1.0',
      commit: 'bbb2222ccc3333',
    },
    {
      name: 'document-indexer',
      status: 'down',
      type: 'service',
      version: '1.0.0',
      commit: 'ccc3333ddd4444',
    },
    { name: 'document-lister', status: 'up', type: 'service', version: '1.0.1' },
    { name: 'admin', status: 'up', type: 'service', version: '0.9.0', commit: 'eee5555fff6666' },
    { name: 'aithena-ui', status: 'up', type: 'service', version: '2.0.0' },
    { name: 'solr', status: 'up', type: 'infrastructure', version: '9.4' },
    { name: 'redis', status: 'up', type: 'infrastructure', version: '7.2' },
    { name: 'rabbitmq', status: 'down', type: 'infrastructure', version: '3.12' },
    { name: 'nginx', status: 'up', type: 'infrastructure', version: '1.25' },
    { name: 'zookeeper', status: 'unknown', type: 'infrastructure', version: '3.9' },
  ],
  total: 11,
  healthy: 8,
  last_updated: '2025-07-18T10:00:00Z',
};

/* ── Helpers ──────────────────────────────────────────────────────────── */

function createMockFetch(overrides?: { data?: object; status?: number }) {
  const data = overrides?.data ?? mockContainersResponse;
  const status = overrides?.status ?? 200;

  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => (status >= 200 && status < 300 ? data : { detail: 'Containers error' }),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function renderPage() {
  return render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
}

/* ── Tests ────────────────────────────────────────────────────────────── */

describe('AdminSystemStatusPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('shows loading state initially', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    renderPage();
    expect(screen.getByText(/loading system status/i)).toBeInTheDocument();
  });

  it('renders container overview metrics', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('11')).toBeInTheDocument();
    });

    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    expect(screen.getByText('Total Containers')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('Needs Attention')).toBeInTheDocument();
  });

  it('renders application services with status emojis', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    expect(screen.getByText('embeddings-server')).toBeInTheDocument();
    expect(screen.getByText('document-indexer')).toBeInTheDocument();
    expect(screen.getByText('document-lister')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('aithena-ui')).toBeInTheDocument();

    // Status emojis
    const emojis = screen.getAllByText('🟢');
    expect(emojis.length).toBeGreaterThanOrEqual(5);
    expect(screen.getAllByText('🔴').length).toBeGreaterThanOrEqual(1);
  });

  it('renders infrastructure services', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr')).toBeInTheDocument();
    });

    expect(screen.getByText('redis')).toBeInTheDocument();
    expect(screen.getByText('rabbitmq')).toBeInTheDocument();
    expect(screen.getByText('nginx')).toBeInTheDocument();
    expect(screen.getByText('zookeeper')).toBeInTheDocument();

    // Unknown status
    expect(screen.getAllByText('🟠').length).toBeGreaterThanOrEqual(1);
  });

  it('shows version and commit info on service cards', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    // Version
    expect(screen.getByText(/1\.2\.0/)).toBeInTheDocument();
    // Commit (truncated to 7 chars)
    expect(screen.getByText('abc1234')).toBeInTheDocument();
  });

  it('shows error banner when API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ status: 500 }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Containers error/)).toBeInTheDocument();
    });

    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows error banner with stale data on refresh failure', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('11')).toBeInTheDocument();
    });

    // Now make fetch fail
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({ detail: 'Server down' }),
        })
      )
    );

    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(screen.getByText(/Server down/)).toBeInTheDocument();
    });

    // Stale data should still show
    expect(screen.getByText('11')).toBeInTheDocument();
  });

  it('refresh button fetches data again', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('11')).toBeInTheDocument();
    });

    const callsBefore = mockFetch.mock.calls.length;
    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it('auto-refreshes every 30 seconds', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('11')).toBeInTheDocument();
    });

    const initialCalls = mockFetch.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(initialCalls);
    });
  });

  it('renders section headings', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Application Services')).toBeInTheDocument();
    });

    expect(screen.getByText('Infrastructure Services')).toBeInTheDocument();
  });

  it('shows last-refreshed timestamp', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/last updated/i)).toBeInTheDocument();
    });
  });

  it('handles all-healthy state without needs-attention highlight', async () => {
    const allHealthy = {
      ...mockContainersResponse,
      containers: mockContainersResponse.containers.map((c) => ({
        ...c,
        status: 'up',
      })),
      total: 11,
      healthy: 11,
    };
    vi.stubGlobal('fetch', createMockFetch({ data: allHealthy }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Application Services')).toBeInTheDocument();
    });

    // Needs attention should be 0
    const metricsSection = screen.getByLabelText(/container overview metrics/i);
    expect(metricsSection).toHaveTextContent('0');
    // All 11 healthy
    expect(metricsSection).toHaveTextContent('11');
  });

  it('handles empty containers response', async () => {
    const empty = {
      containers: [],
      total: 0,
      healthy: 0,
      last_updated: '2025-07-18T10:00:00Z',
    };
    vi.stubGlobal('fetch', createMockFetch({ data: empty }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Application Services')).toBeInTheDocument();
    });

    expect(screen.getAllByText(/no services found/i).length).toBe(2);
  });

  it('has correct aria-labels for accessibility', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    expect(screen.getByRole('main', { name: /system status/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/container overview metrics/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/application services status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/infrastructure services status/i)).toBeInTheDocument();
  });
});
