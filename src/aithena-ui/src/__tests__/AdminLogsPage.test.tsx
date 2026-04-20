import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import AdminLogsPage from '../pages/AdminLogsPage';
import { IntlWrapper } from './test-intl-wrapper';

/* ── Mock data ────────────────────────────────────────────────────────── */

const mockContainers = {
  containers: [
    { name: 'solr-search', status: 'up' },
    { name: 'embeddings-server', status: 'up' },
    { name: 'document-indexer', status: 'up' },
  ],
  total: 3,
  healthy: 3,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockLogText = [
  '2025-07-18T10:00:01Z INFO  Starting service',
  '2025-07-18T10:00:02Z DEBUG Processing request',
  '2025-07-18T10:00:03Z WARN  High memory usage',
  '2025-07-18T10:00:04Z ERROR Connection timeout',
  '2025-07-18T10:00:05Z INFO  Request completed',
].join('\n');

/* ── Helpers ──────────────────────────────────────────────────────────── */

function createMockFetch(overrides?: {
  containersStatus?: number;
  logsStatus?: number;
  logText?: string;
}) {
  const cs = overrides?.containersStatus ?? 200;
  const ls = overrides?.logsStatus ?? 200;
  const logContent = overrides?.logText ?? mockLogText;

  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({
        ok: cs >= 200 && cs < 300,
        status: cs,
        json: async () =>
          cs >= 200 && cs < 300 ? mockContainers : { detail: 'Containers unavailable' },
      });
    }
    if (url.includes('/v1/admin/logs/')) {
      return Promise.resolve({
        ok: ls >= 200 && ls < 300,
        status: ls,
        text: async () => logContent,
        json: async () => ({ detail: 'Log API error' }),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function renderLogsPage() {
  return render(<AdminLogsPage />, { wrapper: IntlWrapper });
}

/* ── Tests ────────────────────────────────────────────────────────────── */

describe('AdminLogsPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('renders the page title and controls', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderLogsPage();

    expect(screen.getByText('Log Viewer')).toBeInTheDocument();
    expect(screen.getByLabelText(/service/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tail lines/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/toggle auto-refresh/i)).toBeInTheDocument();
  });

  it('populates the service selector from the containers API', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    expect(screen.getByText('embeddings-server')).toBeInTheDocument();
    expect(screen.getByText('document-indexer')).toBeInTheDocument();
  });

  it('shows hint to select a service before logs are loaded', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    expect(screen.getByText(/select a service above/i)).toBeInTheDocument();
  });

  it('fetches and displays logs when a service is selected', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    const selector = screen.getByLabelText(/service/i);
    await user.selectOptions(selector, 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/connection timeout/i)).toBeInTheDocument();
  });

  it('passes tail parameter when fetching logs', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    // Change tail lines to 500
    const tailSelect = screen.getByLabelText(/tail lines/i);
    await user.selectOptions(tailSelect, '500');

    const serviceSelect = screen.getByLabelText(/service/i);
    await user.selectOptions(serviceSelect, 'solr-search');

    await waitFor(() => {
      const logCalls = mockFetch.mock.calls.filter((c: string[]) =>
        c[0].includes('/v1/admin/logs/')
      );
      expect(logCalls.length).toBeGreaterThan(0);
      expect(logCalls[logCalls.length - 1][0]).toContain('tail=500');
    });
  });

  it('filters log lines by search text', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    const searchInput = screen.getByLabelText(/search within logs/i);
    await user.type(searchInput, 'ERROR');

    await waitFor(() => {
      expect(screen.getByText(/showing 1 of 5 lines/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/connection timeout/i)).toBeInTheDocument();
    expect(screen.queryByText(/starting service/i)).not.toBeInTheDocument();
  });

  it('shows error banner when containers API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ containersStatus: 500 }));
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText(/could not load services/i)).toBeInTheDocument();
    });
  });

  it('shows error banner when logs API fails', async () => {
    vi.stubGlobal('fetch', createMockFetch({ logsStatus: 500 }));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/could not load logs/i)).toBeInTheDocument();
    });
  });

  it('gracefully handles missing log API with info message', async () => {
    vi.stubGlobal('fetch', createMockFetch({ containersStatus: 503 }));
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/could not load services/i)).toBeInTheDocument();
  });

  it('auto-refresh fetches logs periodically when enabled', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    // Enable auto-refresh
    const autoRefreshCheckbox = screen.getByLabelText(/toggle auto-refresh/i);
    await user.click(autoRefreshCheckbox);
    expect(autoRefreshCheckbox).toBeChecked();

    const callsBefore = mockFetch.mock.calls.filter((c: string[]) =>
      c[0].includes('/v1/admin/logs/')
    ).length;

    // Advance 31 seconds (default interval is 30s)
    await act(async () => {
      vi.advanceTimersByTime(31_000);
    });

    await waitFor(() => {
      const callsAfter = mockFetch.mock.calls.filter((c: string[]) =>
        c[0].includes('/v1/admin/logs/')
      ).length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  it('does not auto-refresh when checkbox is unchecked', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    // Auto-refresh is off by default
    const autoRefreshCheckbox = screen.getByLabelText(/toggle auto-refresh/i);
    expect(autoRefreshCheckbox).not.toBeChecked();

    const callsBefore = mockFetch.mock.calls.filter((c: string[]) =>
      c[0].includes('/v1/admin/logs/')
    ).length;

    await act(async () => {
      vi.advanceTimersByTime(31_000);
    });

    const callsAfter = mockFetch.mock.calls.filter((c: string[]) =>
      c[0].includes('/v1/admin/logs/')
    ).length;
    expect(callsAfter).toBe(callsBefore);
  });

  it('refresh button re-fetches logs', async () => {
    const mockFetch = createMockFetch();
    vi.stubGlobal('fetch', mockFetch);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    const callsBefore = mockFetch.mock.calls.filter((c: string[]) =>
      c[0].includes('/v1/admin/logs/')
    ).length;

    const refreshBtn = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      const callsAfter = mockFetch.mock.calls.filter((c: string[]) =>
        c[0].includes('/v1/admin/logs/')
      ).length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  it('tail lines selector has all expected options', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    renderLogsPage();

    const tailSelect = screen.getByLabelText(/tail lines/i);
    const options = tailSelect.querySelectorAll('option');
    const values = Array.from(options).map((o) => o.getAttribute('value'));
    expect(values).toEqual(['50', '100', '200', '500', '1000']);
  });

  it('shows interval selector when auto-refresh is enabled', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    // Initially no interval selector
    expect(screen.queryByLabelText(/refresh interval/i)).not.toBeInTheDocument();

    // Enable auto-refresh
    await user.click(screen.getByLabelText(/toggle auto-refresh/i));

    expect(screen.getByLabelText(/refresh interval/i)).toBeInTheDocument();
  });

  it('renders log output in a pre/code block', async () => {
    vi.stubGlobal('fetch', createMockFetch());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogsPage();

    await waitFor(() => {
      expect(screen.getByText('solr-search')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText(/service/i), 'solr-search');

    await waitFor(() => {
      expect(screen.getByText(/starting service/i)).toBeInTheDocument();
    });

    const logOutput = screen.getByLabelText(/log output/i);
    expect(logOutput.tagName).toBe('PRE');
    expect(logOutput.querySelector('code')).toBeInTheDocument();
  });

  it('does not have Docker socket dependency', () => {
    // Verify the page component source doesn't reference Docker socket
    const pageSource = AdminLogsPage.toString();
    expect(pageSource).not.toContain('docker.sock');
    expect(pageSource).not.toContain('/var/run/docker');
  });
});
