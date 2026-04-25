import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import AdminInfrastructurePage from '../pages/AdminInfrastructurePage';
import { IntlWrapper } from './test-intl-wrapper';

/* ── Mock data ────────────────────────────────────────────────────────── */

const mockInfrastructure = {
  services: [
    { name: 'solr', url: 'http://solr:8983', status: 'connected', type: 'search' },
    { name: 'rabbitmq', url: 'amqp://rabbitmq:5672', status: 'connected', type: 'queue' },
    { name: 'redis', url: 'redis://redis:6379', status: 'disconnected', type: 'cache' },
  ],
  solr_admin_url: '/admin/solr/',
  rabbitmq_admin_url: '/admin/rabbitmq/',
  redis_admin_url: '/admin/redis/',
};

/* ── Helpers ──────────────────────────────────────────────────────────── */

function createMockFetch(options?: { status?: number; data?: object }) {
  const status = options?.status ?? 200;
  const data = options?.data ?? mockInfrastructure;

  return vi.fn().mockImplementation(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: async () => (status >= 200 && status < 300 ? data : { detail: 'Infrastructure error' }),
    })
  );
}

function renderPage() {
  return render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });
}

/* ── Tests ────────────────────────────────────────────────────────────── */

describe('AdminInfrastructurePage', () => {
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
    expect(screen.getByText(/loading infrastructure/i)).toBeInTheDocument();
  });

  it('renders page title', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 2, name: /infrastructure/i })
      ).toBeInTheDocument();
    });
  });

  it('renders three service link cards', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    });

    expect(screen.getByText('RabbitMQ Management')).toBeInTheDocument();
    expect(screen.getByText('Redis Commander')).toBeInTheDocument();
  });

  it('service cards link to correct URLs', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    });

    const solrLink = screen.getByText('Solr Admin').closest('a');
    const rabbitmqLink = screen.getByText('RabbitMQ Management').closest('a');
    const redisLink = screen.getByText('Redis Commander').closest('a');

    expect(solrLink).toHaveAttribute('href', '/admin/solr/');
    expect(rabbitmqLink).toHaveAttribute('href', '/admin/rabbitmq/');
    expect(redisLink).toHaveAttribute('href', '/admin/redis/');
  });

  it('external links have proper security attributes', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    });

    const links = screen.getAllByRole('link');
    links.forEach((link) => {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  it('renders connection details table with service data', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Connection Details')).toBeInTheDocument();
    });

    expect(screen.getByText('solr')).toBeInTheDocument();
    expect(screen.getByText('http://solr:8983')).toBeInTheDocument();
    expect(screen.getByText('rabbitmq')).toBeInTheDocument();
    expect(screen.getByText('redis')).toBeInTheDocument();

    // Check table structure: header + 3 data rows
    const rows = screen.getAllByRole('row');
    expect(rows.length).toBe(4);
  });

  it('shows status badges in connection table', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr')).toBeInTheDocument();
    });

    const connectedBadges = screen.getAllByText('connected');
    const disconnectedBadges = screen.getAllByText('disconnected');
    expect(connectedBadges.length).toBe(2);
    expect(disconnectedBadges.length).toBe(1);
  });

  it('shows error banner when API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ status: 500 }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Infrastructure error/)).toBeInTheDocument();
  });

  it('still renders cards with defaults when API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ status: 500 }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    // Cards should still render with default URLs
    expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    expect(screen.getByText('RabbitMQ Management')).toBeInTheDocument();
    expect(screen.getByText('Redis Commander')).toBeInTheDocument();
  });

  it('does not show connection table when API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ status: 500 }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.queryByText('Connection Details')).not.toBeInTheDocument();
  });

  it('refresh button fetches data again', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('solr')).toBeInTheDocument();
    });

    const callsBefore = mockFetch.mock.calls.length;
    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it('uses API-provided URLs when available', async () => {
    const customData = {
      ...mockInfrastructure,
      solr_admin_url: '/custom/solr/',
      rabbitmq_admin_url: '/custom/rabbitmq/',
      redis_admin_url: '/custom/redis/',
    };
    vi.stubGlobal('fetch', createMockFetch({ data: customData }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    });

    const solrLink = screen.getByText('Solr Admin').closest('a');
    expect(solrLink).toHaveAttribute('href', '/custom/solr/');
  });

  it('renders with empty services array', async () => {
    const emptyServices = { ...mockInfrastructure, services: [] };
    vi.stubGlobal('fetch', createMockFetch({ data: emptyServices }));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Solr Admin')).toBeInTheDocument();
    });

    // No connection table when services empty
    expect(screen.queryByText('Connection Details')).not.toBeInTheDocument();
  });

  it('handles network errors gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network failure')));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Network failure/)).toBeInTheDocument();
  });
});
