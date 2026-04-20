import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import AdminDashboardPage from '../pages/AdminDashboardPage';
import { IntlWrapper } from './test-intl-wrapper';

/* ── Mock data ────────────────────────────────────────────────────────── */

const mockDocuments = {
  total: 150,
  queued: 12,
  processed: 130,
  failed: 8,
  documents: [],
};

const mockQueue = {
  queue_name: 'shortembeddings',
  messages_ready: 5,
  messages_unacknowledged: 2,
  messages_total: 7,
  consumers: 3,
  status: 'ok',
};

const mockInfrastructure = {
  containers: [
    { name: 'solr-search', status: 'up', type: 'service', version: '1.0.0' },
    { name: 'embeddings-server', status: 'up', type: 'service', version: '1.0.0' },
    { name: 'redis', status: 'up', type: 'infrastructure', version: '7.2' },
    { name: 'rabbitmq', status: 'down', type: 'infrastructure', version: '3.12' },
  ],
  total: 4,
  healthy: 3,
  last_updated: '2025-07-18T10:00:00Z',
};

/* ── Helpers ──────────────────────────────────────────────────────────── */

function createMockFetch(overrides: {
  documents?: object | null;
  queue?: object | null;
  infra?: object | null;
  documentsStatus?: number;
  queueStatus?: number;
  infraStatus?: number;
}) {
  const docs = overrides.documents ?? mockDocuments;
  const q = overrides.queue ?? mockQueue;
  const inf = overrides.infra ?? mockInfrastructure;
  const ds = overrides.documentsStatus ?? 200;
  const qs = overrides.queueStatus ?? 200;
  const is = overrides.infraStatus ?? 200;

  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/documents')) {
      return Promise.resolve({
        ok: ds >= 200 && ds < 300,
        status: ds,
        json: async () => (ds >= 200 && ds < 300 ? docs : { detail: 'Documents error' }),
      });
    }
    if (url.includes('/v1/admin/queue-status')) {
      return Promise.resolve({
        ok: qs >= 200 && qs < 300,
        status: qs,
        json: async () => (qs >= 200 && qs < 300 ? q : { detail: 'Queue error' }),
      });
    }
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({
        ok: is >= 200 && is < 300,
        status: is,
        json: async () => (is >= 200 && is < 300 ? inf : { detail: 'Infrastructure error' }),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function renderDashboard() {
  return render(<AdminDashboardPage />, { wrapper: IntlWrapper });
}

/* ── Tests ────────────────────────────────────────────────────────────── */

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('shows loading state initially', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    renderDashboard();
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
  });

  it('renders all three metric sections when data loads', async () => {
    vi.stubGlobal('fetch', createMockFetch({}));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    // Document metrics
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('130')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();

    // Queue metrics
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();

    // Infrastructure
    expect(screen.getByText('solr-search')).toBeInTheDocument();
    expect(screen.getByText('rabbitmq')).toBeInTheDocument();
    expect(screen.getByText(/3 \/ 4 services healthy/i)).toBeInTheDocument();
    expect(screen.getByText(/1 service degraded/i)).toBeInTheDocument();
  });

  it('shows queue metadata (queue name and consumers)', async () => {
    vi.stubGlobal('fetch', createMockFetch({}));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('shortembeddings')).toBeInTheDocument();
    });
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows error banners when individual API calls fail', async () => {
    vi.stubGlobal('fetch', createMockFetch({ documentsStatus: 500, queueStatus: 502 }));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/Documents error/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Queue error/)).toBeInTheDocument();
    // Infrastructure should still render
    expect(screen.getByText('solr-search')).toBeInTheDocument();
  });

  it('refresh button fetches data again', async () => {
    const mockFetch = createMockFetch({});
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const callsBefore = mockFetch.mock.calls.length;
    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it('auto-refresh checkbox toggles polling', async () => {
    const mockFetch = createMockFetch({});
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const checkbox = screen.getByRole('checkbox', { name: /auto-refresh/i });
    expect(checkbox).toBeChecked();

    // Disable auto-refresh
    await user.click(checkbox);
    expect(checkbox).not.toBeChecked();

    const callsAfterDisable = mockFetch.mock.calls.length;

    // Advance 31 seconds — no new calls expected
    await act(async () => {
      vi.advanceTimersByTime(31_000);
    });
    expect(mockFetch.mock.calls.length).toBe(callsAfterDisable);

    // Re-enable auto-refresh
    await user.click(checkbox);
    expect(checkbox).toBeChecked();

    // Advance 31 seconds — new calls expected
    await act(async () => {
      vi.advanceTimersByTime(31_000);
    });
    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterDisable);
  });

  it('auto-refresh triggers fetch every 30 seconds', async () => {
    const mockFetch = createMockFetch({});
    vi.stubGlobal('fetch', mockFetch);
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const initialCalls = mockFetch.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(initialCalls);
    });
  });

  it('renders infrastructure table with service status badges', async () => {
    vi.stubGlobal('fetch', createMockFetch({}));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    const rows = screen.getAllByRole('row');
    // header row + 4 data rows
    expect(rows.length).toBe(5);

    // Check status badges exist
    const upBadges = screen.getAllByText('up');
    const downBadges = screen.getAllByText('down');
    expect(upBadges.length).toBe(3);
    expect(downBadges.length).toBe(1);
  });

  it('gracefully shows sections that load even when others fail', async () => {
    vi.stubGlobal('fetch', createMockFetch({ infraStatus: 503 }));
    renderDashboard();

    await waitFor(() => {
      // Documents and queue should still render
      expect(screen.getByText('150')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    // Infrastructure error shown
    expect(screen.getByText(/Infrastructure error/)).toBeInTheDocument();
    // But no infra table
    expect(screen.queryByText('solr-search')).not.toBeInTheDocument();
  });

  it('does not show degraded warning when all services healthy', async () => {
    const allHealthy = {
      ...mockInfrastructure,
      containers: mockInfrastructure.containers.map((c) => ({ ...c, status: 'up' })),
      healthy: 4,
    };
    vi.stubGlobal('fetch', createMockFetch({ infra: allHealthy }));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/4 \/ 4 services healthy/i)).toBeInTheDocument();
    });

    expect(screen.queryByText(/degraded/i)).not.toBeInTheDocument();
  });
});
