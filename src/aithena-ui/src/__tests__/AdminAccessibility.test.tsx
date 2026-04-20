import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, afterEach, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { checkAccessibility } from './a11y-setup';
import { IntlWrapper } from './test-intl-wrapper';

import AdminDashboardPage from '../pages/AdminDashboardPage';
import AdminReindexPage from '../pages/AdminReindexPage';
import AdminInfrastructurePage from '../pages/AdminInfrastructurePage';
import AdminLogsPage from '../pages/AdminLogsPage';
import AdminSystemStatusPage from '../pages/AdminSystemStatusPage';
import AdminIndexingStatusPage from '../pages/AdminIndexingStatusPage';
import AdminDocumentsPage from '../pages/AdminDocumentsPage';
import AdminSidebar from '../Components/AdminSidebar';

/* ── Shared mock data ─────────────────────────────────────────────────── */

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

const mockInfraContainers = {
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

const mockInfrastructurePage = {
  services: [
    { name: 'solr', url: 'http://solr:8983', status: 'connected', type: 'search' },
    { name: 'rabbitmq', url: 'amqp://rabbitmq:5672', status: 'connected', type: 'queue' },
    { name: 'redis', url: 'redis://redis:6379', status: 'disconnected', type: 'cache' },
  ],
  solr_admin_url: '/admin/solr/',
  rabbitmq_admin_url: '/admin/rabbitmq/',
  redis_admin_url: '/admin/redis/',
};

const mockSystemStatus = {
  containers: [
    { name: 'solr-search', status: 'up', type: 'service', version: '1.2.0', commit: 'abc1234' },
    { name: 'redis', status: 'up', type: 'infrastructure', version: '7.2' },
  ],
  total: 2,
  healthy: 2,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockLogsContainers = {
  containers: [
    { name: 'solr-search', status: 'up' },
    { name: 'embeddings-server', status: 'up' },
  ],
  total: 2,
  healthy: 2,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockIndexingStatus = {
  summary: {
    total: 10,
    queued: 2,
    processing: 1,
    processed: 6,
    failed: 1,
    total_pages: 1000,
    total_chunks: 3000,
  },
  documents: [
    {
      id: 'doc-1',
      status: 'processed',
      path: '/data/test.pdf',
      title: 'Test Book',
      text_indexed: true,
      embedding_indexed: true,
      page_count: 100,
      chunk_count: 300,
      error: null,
      error_stage: null,
      timestamp: '2024-01-15T10:00:00Z',
    },
  ],
};

const mockDocumentsPage = {
  total: 3,
  queued: 1,
  processed: 1,
  failed: 1,
  documents: [
    { id: 'q1', status: 'queued', path: '/data/pending.pdf', timestamp: '2024-01-15T10:00:00' },
    {
      id: 'p1',
      status: 'processed',
      path: '/data/done.pdf',
      title: 'Done Book',
      author: 'Author',
      year: 2023,
      page_count: 100,
      chunk_count: 40,
      timestamp: '2024-01-14T09:00:00',
    },
    {
      id: 'f1',
      status: 'failed',
      path: '/data/broken.pdf',
      error: 'Extraction failed',
      timestamp: '2024-01-13T08:00:00',
    },
  ],
};

/* ── Mock fetch helpers ───────────────────────────────────────────────── */

function createDashboardFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/documents')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockDocuments });
    }
    if (url.includes('/v1/admin/queue-status')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockQueue });
    }
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockInfraContainers });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function createInfraFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => mockInfrastructurePage,
  });
}

function createSystemStatusFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockSystemStatus });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function createLogsFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/containers')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockLogsContainers });
    }
    if (url.includes('/v1/admin/logs/')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => 'INFO  Starting service\nDEBUG Processing',
        json: async () => ({}),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  });
}

function createIndexingFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => mockIndexingStatus,
  });
}

function createDocumentsFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => mockDocumentsPage,
  });
}

/* ═══════════════════════════════════════════════════════════════════════
   Accessibility Tests — WCAG 2.1 AA
   ═══════════════════════════════════════════════════════════════════════ */

describe('Accessibility (WCAG 2.1 AA)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  /* ── AdminSidebar ──────────────────────────────────────────────────── */

  describe('AdminSidebar', () => {
    function renderSidebar(path = '/admin') {
      return render(
        <IntlWrapper>
          <MemoryRouter initialEntries={[path]}>
            <AdminSidebar />
          </MemoryRouter>
        </IntlWrapper>
      );
    }

    it('should have no critical accessibility violations', async () => {
      const { container } = renderSidebar();
      await checkAccessibility(container);
    });

    it('has accessible navigation landmark with label', () => {
      renderSidebar();
      const nav = screen.getByRole('navigation', { name: /admin navigation/i });
      expect(nav).toBeInTheDocument();
    });

    it('all interactive elements are reachable via Tab', async () => {
      renderSidebar();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const links = screen.getAllByRole('link');

      for (const link of links) {
        await user.tab();
        expect(link).toHaveFocus();
      }
    });

    it('active link has aria-current="page"', () => {
      renderSidebar();
      const activeLink = screen.getByText('Dashboard').closest('a');
      expect(activeLink).toHaveAttribute('aria-current', 'page');
    });

    it('icons are hidden from assistive technology', () => {
      renderSidebar();
      const nav = screen.getByRole('navigation');
      const hiddenIcons = nav.querySelectorAll('[aria-hidden="true"]');
      expect(hiddenIcons.length).toBeGreaterThan(0);
    });

    it('supports arrow key navigation', async () => {
      renderSidebar();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      const dashboardLink = screen.getByText('Dashboard').closest('a')!;
      dashboardLink.focus();

      await user.keyboard('{ArrowDown}');
      expect(document.activeElement).toBe(screen.getByText('Document Manager').closest('a'));

      await user.keyboard('{ArrowUp}');
      expect(document.activeElement).toBe(screen.getByText('Dashboard').closest('a'));
    });

    it('supports Home/End keyboard navigation', async () => {
      renderSidebar();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      const dashboardLink = screen.getByText('Dashboard').closest('a')!;
      dashboardLink.focus();

      await user.keyboard('{End}');
      expect(document.activeElement).toBe(screen.getByText('Backup Dashboard').closest('a'));

      await user.keyboard('{Home}');
      expect(document.activeElement).toBe(screen.getByText('Dashboard').closest('a'));
    });
  });

  /* ── AdminDashboardPage ────────────────────────────────────────────── */

  describe('AdminDashboardPage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createDashboardFetch());
      const { container } = render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('interactive elements have accessible labels', async () => {
      vi.stubGlobal('fetch', createDashboardFetch());
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: /auto-refresh/i })).toBeInTheDocument();
    });

    it('error banners use role="alert"', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockImplementation((url: string) => {
          if (url.includes('/v1/admin/documents')) {
            return Promise.resolve({
              ok: false,
              status: 500,
              json: async () => ({ detail: 'Documents error' }),
            });
          }
          if (url.includes('/v1/admin/queue-status')) {
            return Promise.resolve({ ok: true, status: 200, json: async () => mockQueue });
          }
          if (url.includes('/v1/admin/containers')) {
            return Promise.resolve({
              ok: true,
              status: 200,
              json: async () => mockInfraContainers,
            });
          }
          return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
        })
      );

      render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });

    it('sections have accessible labels', async () => {
      vi.stubGlobal('fetch', createDashboardFetch());
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
      });

      const sections = screen.getAllByRole('region');
      expect(sections.length).toBeGreaterThan(0);
    });

    it('table has proper scope attributes on headers', async () => {
      vi.stubGlobal('fetch', createDashboardFetch());
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      const thElements = screen.getAllByRole('columnheader');
      thElements.forEach((th) => {
        expect(th).toHaveAttribute('scope', 'col');
      });
    });

    it('dashboard interactive elements are reachable via Tab', async () => {
      vi.stubGlobal('fetch', createDashboardFetch());
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument();
      });

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const checkbox = screen.getByRole('checkbox', { name: /auto-refresh/i });
      const button = screen.getByRole('button', { name: /refresh/i });

      await user.tab();
      expect(checkbox).toHaveFocus();

      await user.tab();
      expect(button).toHaveFocus();
    });
  });

  /* ── AdminReindexPage ──────────────────────────────────────────────── */

  describe('AdminReindexPage', () => {
    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminReindexPage />, { wrapper: IntlWrapper });
      await checkAccessibility(container);
    });

    it('reindex button is accessible', () => {
      render(<AdminReindexPage />, { wrapper: IntlWrapper });

      const button = screen.getByRole('button', { name: /start full reindex/i });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('type', 'button');
    });

    it('error status uses role="alert" and aria-live="assertive"', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: false,
          status: 500,
          json: async () => ({ detail: 'Test error' }),
        })
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<AdminReindexPage />, { wrapper: IntlWrapper });

      await user.click(screen.getByRole('button', { name: /start full reindex/i }));
      await user.click(screen.getByRole('button', { name: /confirm reindex/i }));

      await waitFor(() => {
        const alert = screen.getByRole('alert');
        expect(alert).toHaveAttribute('aria-live', 'assertive');
      });
    });

    it('description section has aria-label', () => {
      render(<AdminReindexPage />, { wrapper: IntlWrapper });
      expect(screen.getByLabelText(/reindex process description/i)).toBeInTheDocument();
    });
  });

  /* ── AdminInfrastructurePage ───────────────────────────────────────── */

  describe('AdminInfrastructurePage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createInfraFetch());
      const { container } = render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Solr Admin')).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('has main landmark', async () => {
      vi.stubGlobal('fetch', createInfraFetch());
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Solr Admin')).toBeInTheDocument();
      });

      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('external links have rel="noopener noreferrer"', async () => {
      vi.stubGlobal('fetch', createInfraFetch());
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Solr Admin')).toBeInTheDocument();
      });

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('connection table has proper scope attributes', async () => {
      vi.stubGlobal('fetch', createInfraFetch());
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Connection Details')).toBeInTheDocument();
      });

      const thElements = screen.getAllByRole('columnheader');
      thElements.forEach((th) => {
        expect(th).toHaveAttribute('scope', 'col');
      });
    });
  });

  /* ── AdminLogsPage ─────────────────────────────────────────────────── */

  describe('AdminLogsPage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createLogsFetch());
      const { container } = render(<AdminLogsPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Log Viewer')).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('form controls have associated labels', async () => {
      vi.stubGlobal('fetch', createLogsFetch());
      render(<AdminLogsPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('Log Viewer')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/service/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/tail lines/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/search within logs/i)).toBeInTheDocument();
    });

    it('has main landmark', () => {
      vi.stubGlobal('fetch', createLogsFetch());
      render(<AdminLogsPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('refresh button has accessible label', () => {
      vi.stubGlobal('fetch', createLogsFetch());
      render(<AdminLogsPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  /* ── AdminSystemStatusPage ─────────────────────────────────────────── */

  describe('AdminSystemStatusPage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createSystemStatusFetch());
      const { container } = render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('has main landmark with aria-label', async () => {
      vi.stubGlobal('fetch', createSystemStatusFetch());
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      const main = screen.getByRole('main');
      expect(main).toHaveAttribute('aria-label');
    });

    it('service cards have accessible labels', async () => {
      vi.stubGlobal('fetch', createSystemStatusFetch());
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/solr-search.*healthy/i)).toBeInTheDocument();
    });

    it('metrics section has aria-label', async () => {
      vi.stubGlobal('fetch', createSystemStatusFetch());
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/container overview metrics/i)).toBeInTheDocument();
    });

    it('last refreshed timestamp uses aria-live', async () => {
      vi.stubGlobal('fetch', createSystemStatusFetch());
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('solr-search')).toBeInTheDocument();
      });

      const liveRegion = screen.getByText(/last updated/i);
      expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    });
  });

  /* ── AdminIndexingStatusPage ───────────────────────────────────────── */

  describe('AdminIndexingStatusPage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createIndexingFetch());
      const { container } = render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('has main landmark', () => {
      vi.stubGlobal('fetch', createIndexingFetch());
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('filter buttons use aria-pressed', async () => {
      vi.stubGlobal('fetch', createIndexingFetch());
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument();
      });

      const allButton = screen.getByRole('button', { name: /^all$/i });
      expect(allButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('metrics section has aria-label', async () => {
      vi.stubGlobal('fetch', createIndexingFetch());
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/indexing summary metrics/i)).toBeInTheDocument();
    });

    it('table headers have scope="col"', async () => {
      vi.stubGlobal('fetch', createIndexingFetch());
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument();
      });

      const thElements = screen.getAllByRole('columnheader');
      thElements.forEach((th) => {
        expect(th).toHaveAttribute('scope', 'col');
      });
    });
  });

  /* ── AdminDocumentsPage ────────────────────────────────────────────── */

  describe('AdminDocumentsPage', () => {
    it('should have no critical accessibility violations', async () => {
      vi.stubGlobal('fetch', createDocumentsFetch());
      const { container } = render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText(/document manager/i)).toBeInTheDocument();
      });

      await checkAccessibility(container);
    });

    it('tab controls use proper ARIA attributes', async () => {
      vi.stubGlobal('fetch', createDocumentsFetch());
      render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText(/document manager/i)).toBeInTheDocument();
      });

      const tablist = screen.getByRole('tablist');
      expect(tablist).toBeInTheDocument();

      const tabs = screen.getAllByRole('tab');
      expect(tabs.length).toBeGreaterThan(0);

      const selectedTab = tabs.find((t) => t.getAttribute('aria-selected') === 'true');
      expect(selectedTab).toBeTruthy();
    });

    it('search input has accessible label', async () => {
      vi.stubGlobal('fetch', createDocumentsFetch());
      render(<AdminDocumentsPage />, { wrapper: IntlWrapper });

      await waitFor(() => {
        expect(screen.getByText(/document manager/i)).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/search|filter/i)).toBeInTheDocument();
    });
  });
});
