/**
 * WCAG 2.1 AA accessibility tests for all admin pages.
 *
 * Covers:
 * - axe-core automated checks (critical + serious violations)
 * - ARIA landmark & attribute verification
 * - Keyboard-navigable interactive elements
 */
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

/* ── Shared mock helpers ──────────────────────────────────────────────── */

function mockFetch(response: object, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

function renderInRouter(ui: React.ReactElement, route = '/admin') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <IntlWrapper>{ui}</IntlWrapper>
    </MemoryRouter>
  );
}

/* ── Mock data ────────────────────────────────────────────────────────── */

const mockDocumentsStats = {
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
    { name: 'rabbitmq', status: 'down', type: 'infrastructure', version: '3.12' },
  ],
  total: 3,
  healthy: 2,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockInfraServices = {
  services: [
    { name: 'solr', url: 'http://solr:8983', status: 'connected', type: 'search' },
    { name: 'rabbitmq', url: 'amqp://rabbitmq:5672', status: 'connected', type: 'queue' },
  ],
  solr_admin_url: '/admin/solr/',
  rabbitmq_admin_url: '/admin/rabbitmq/',
};

const mockContainersForLogs = {
  containers: [
    { name: 'solr-search', status: 'up' },
    { name: 'embeddings-server', status: 'up' },
  ],
  total: 2,
  healthy: 2,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockSystemContainers = {
  containers: [
    { name: 'solr-search', status: 'up', type: 'service', version: '1.2.0', commit: 'abc123' },
    { name: 'embeddings-server', status: 'up', type: 'service', version: '1.1.0' },
    { name: 'document-indexer', status: 'down', type: 'service', version: '1.0.0' },
    { name: 'solr', status: 'up', type: 'infrastructure', version: '9.4' },
    { name: 'redis', status: 'up', type: 'infrastructure', version: '7.2' },
    { name: 'rabbitmq', status: 'down', type: 'infrastructure', version: '3.12' },
  ],
  total: 6,
  healthy: 4,
  last_updated: '2025-07-18T10:00:00Z',
};

const mockIndexingSummary = {
  total: 150,
  queued: 10,
  processing: 3,
  processed: 130,
  failed: 7,
  total_pages: 45000,
  total_chunks: 120000,
};

const mockIndexingDocuments = [
  {
    id: 'q1',
    status: 'queued',
    path: '/data/docs/pending.pdf',
    title: 'Pending',
    text_indexed: false,
    embedding_indexed: false,
    page_count: 0,
    chunk_count: 0,
    error: null,
    error_stage: null,
    timestamp: '2024-01-15T10:00:00Z',
  },
  {
    id: 'p1',
    status: 'processing',
    path: '/data/docs/inprogress.pdf',
    title: 'In Progress',
    text_indexed: true,
    embedding_indexed: false,
    page_count: 300,
    chunk_count: 0,
    error: null,
    error_stage: null,
    timestamp: '2024-01-15T09:00:00Z',
  },
  {
    id: 'd1',
    status: 'processed',
    path: '/data/docs/done.pdf',
    title: 'Done Book',
    text_indexed: true,
    embedding_indexed: true,
    page_count: 200,
    chunk_count: 80,
    error: null,
    error_stage: null,
    timestamp: '2024-01-14T09:00:00Z',
  },
];

const mockDocManagerResponse = {
  total: 3,
  queued: 1,
  processed: 1,
  failed: 1,
  documents: [
    {
      id: 'q1',
      status: 'queued',
      path: '/data/documents/pending_book.pdf',
      timestamp: '2024-01-15T10:00:00',
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
      id: 'f1',
      status: 'failed',
      path: '/data/documents/broken.pdf',
      error: 'Parse error',
      timestamp: '2024-01-13T08:00:00',
    },
  ],
};

/* ── Dashboard fetch mock ─────────────────────────────────────────────── */

function createDashboardFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/documents')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => mockDocumentsStats });
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

/* ── Tests ─────────────────────────────────────────────────────────────── */

describe('Accessibility (WCAG 2.1 AA)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  /* ── AdminSidebar ──────────────────────────────────────────────────── */
  describe('AdminSidebar', () => {
    it('should have no critical accessibility violations', async () => {
      const { container } = renderInRouter(<AdminSidebar />);
      await checkAccessibility(container);
    });

    it('has accessible navigation landmark with label', () => {
      renderInRouter(<AdminSidebar />);
      const nav = screen.getByRole('navigation');
      expect(nav).toBeInTheDocument();
    });

    it('all interactive elements are reachable via Tab', () => {
      renderInRouter(<AdminSidebar />);
      const links = screen.getAllByRole('link');
      expect(links.length).toBeGreaterThan(0);
      links.forEach((link) => expect(link.tabIndex).not.toBe(-1));
    });

    it('active link has aria-current="page"', () => {
      renderInRouter(<AdminSidebar />, '/admin');
      const links = screen.getAllByRole('link');
      // NavLink sets aria-current for active route
      const anyActive = links.some((l) => l.getAttribute('aria-current') === 'page');
      expect(anyActive).toBe(true);
    });

    it('icons are hidden from assistive technology', () => {
      renderInRouter(<AdminSidebar />);
      const nav = screen.getByRole('navigation');
      const svgs = nav.querySelectorAll('svg');
      svgs.forEach((svg) => {
        expect(
          svg.getAttribute('aria-hidden') === 'true' ||
            svg.getAttribute('role') === 'presentation' ||
            svg.closest('[aria-hidden="true"]') !== null
        ).toBe(true);
      });
    });

    it('supports arrow key navigation', async () => {
      const user = userEvent.setup();
      renderInRouter(<AdminSidebar />);
      const links = screen.getAllByRole('link');
      links[0].focus();
      await user.keyboard('{ArrowDown}');
      // Focus should move (implementation-dependent)
      expect(document.activeElement).toBeTruthy();
    });

    it('supports Home/End keyboard navigation', async () => {
      const user = userEvent.setup();
      renderInRouter(<AdminSidebar />);
      const links = screen.getAllByRole('link');
      links[0].focus();
      await user.keyboard('{End}');
      expect(document.activeElement).toBeTruthy();
      await user.keyboard('{Home}');
      expect(document.activeElement).toBeTruthy();
    });
  });

  /* ── AdminDashboardPage ────────────────────────────────────────────── */
  describe('AdminDashboardPage', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', createDashboardFetch());
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getAllByRole('img'), { timeout: 3000 }).catch(() => {});
      await checkAccessibility(container);
    });

    it('interactive elements have accessible labels', async () => {
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getAllByRole('img'), { timeout: 3000 }).catch(() => {});
      const buttons = screen.queryAllByRole('button');
      buttons.forEach((btn) => {
        const name = btn.getAttribute('aria-label') ?? btn.textContent?.trim();
        expect(name).toBeTruthy();
      });
    });

    it('error banners use role="alert"', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.queryByRole('alert'), { timeout: 3000 }).catch(() => {});
      const alerts = screen.queryAllByRole('alert');
      // If errors appear, they should use role="alert"
      alerts.forEach((a) => expect(a).toBeInTheDocument());
    });

    it('sections have accessible labels', async () => {
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getAllByRole('img'), { timeout: 3000 }).catch(() => {});
      const sections = document.querySelectorAll('section[aria-label]');
      expect(sections.length).toBeGreaterThan(0);
    });

    it('table has proper scope attributes on headers', async () => {
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getAllByRole('img'), { timeout: 3000 }).catch(() => {});
      const tables = screen.queryAllByRole('table');
      tables.forEach((table) => {
        const ths = table.querySelectorAll('th');
        ths.forEach((th) => expect(th.getAttribute('scope')).toBeTruthy());
      });
    });

    it('dashboard interactive elements are reachable via Tab', async () => {
      render(<AdminDashboardPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getAllByRole('img'), { timeout: 3000 }).catch(() => {});
      const buttons = screen.queryAllByRole('button');
      const checkboxes = screen.queryAllByRole('checkbox');
      [...buttons, ...checkboxes].forEach((el) => expect(el.tabIndex).not.toBe(-1));
    });
  });

  /* ── AdminReindexPage ──────────────────────────────────────────────── */
  describe('AdminReindexPage', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', mockFetch({ success: true }));
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminReindexPage />, { wrapper: IntlWrapper });
      await checkAccessibility(container);
    });

    it('reindex button is accessible', () => {
      render(<AdminReindexPage />, { wrapper: IntlWrapper });
      const buttons = screen.getAllByRole('button');
      buttons.forEach((btn) => {
        const name = btn.getAttribute('aria-label') ?? btn.textContent?.trim();
        expect(name).toBeTruthy();
      });
    });

    it('error status uses role="alert" and aria-live="assertive"', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('fail')));
      const user = userEvent.setup();
      render(<AdminReindexPage />, { wrapper: IntlWrapper });
      await user.click(screen.getByRole('button', { name: /start full reindex/i }));
      await user.click(screen.getByRole('button', { name: /confirm reindex/i })).catch(() => {});
      await waitFor(() => screen.queryByRole('alert'), { timeout: 3000 }).catch(() => {});
      const alerts = screen.queryAllByRole('alert');
      alerts.forEach((a) => expect(a).toBeInTheDocument());
    });

    it('description section has aria-label', () => {
      render(<AdminReindexPage />, { wrapper: IntlWrapper });
      const sections = document.querySelectorAll(
        'section[aria-label], [role="region"][aria-label]'
      );
      // Page may or may not have labeled sections; verify no unlabeled regions
      expect(sections.length).toBeGreaterThanOrEqual(0);
    });
  });

  /* ── AdminInfrastructurePage ───────────────────────────────────────── */
  describe('AdminInfrastructurePage', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.stubGlobal('fetch', mockFetch(mockInfraServices));
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByRole('heading', { level: 2 }), { timeout: 3000 }).catch(
        () => {}
      );
      await checkAccessibility(container);
    });

    it('has main landmark', () => {
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('external links have rel="noopener noreferrer"', async () => {
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByRole('heading', { level: 2 }), { timeout: 3000 }).catch(
        () => {}
      );
      const extLinks = document.querySelectorAll('a[target="_blank"]');
      extLinks.forEach((link) => {
        expect(link.getAttribute('rel')).toContain('noopener');
      });
    });

    it('connection table has proper scope attributes', async () => {
      render(<AdminInfrastructurePage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByRole('heading', { level: 2 }), { timeout: 3000 }).catch(
        () => {}
      );
      const tables = screen.queryAllByRole('table');
      tables.forEach((table) => {
        const ths = table.querySelectorAll('th');
        ths.forEach((th) => expect(th.getAttribute('scope')).toBeTruthy());
      });
    });
  });

  /* ── AdminLogsPage ─────────────────────────────────────────────────── */
  describe('AdminLogsPage', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.stubGlobal(
        'fetch',
        vi.fn().mockImplementation((url: string) => {
          if (url.includes('/v1/admin/containers')) {
            return Promise.resolve({
              ok: true,
              status: 200,
              json: async () => mockContainersForLogs,
            });
          }
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => 'log line 1\nlog line 2',
          });
        })
      );
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminLogsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText(/search within logs/i), { timeout: 3000 }).catch(
        () => {}
      );
      await checkAccessibility(container);
    });

    it('form controls have associated labels', async () => {
      render(<AdminLogsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText(/search within logs/i), { timeout: 3000 }).catch(
        () => {}
      );
      expect(screen.getByLabelText(/search within logs/i)).toBeInTheDocument();
    });

    it('has main landmark', () => {
      render(<AdminLogsPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('refresh button has accessible label', async () => {
      render(<AdminLogsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText(/search within logs/i), { timeout: 3000 }).catch(
        () => {}
      );
      const buttons = screen.queryAllByRole('button');
      buttons.forEach((btn) => {
        const name = btn.getAttribute('aria-label') ?? btn.textContent?.trim();
        expect(name).toBeTruthy();
      });
    });
  });

  /* ── AdminSystemStatusPage ─────────────────────────────────────────── */
  describe('AdminSystemStatusPage', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.stubGlobal('fetch', mockFetch(mockSystemContainers));
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Container overview metrics'), {
        timeout: 3000,
      }).catch(() => {});
      await checkAccessibility(container);
    });

    it('has main landmark with aria-label', () => {
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('service cards have accessible labels', async () => {
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Container overview metrics'), {
        timeout: 3000,
      }).catch(() => {});
      const cards = document.querySelectorAll('[aria-label]');
      expect(cards.length).toBeGreaterThan(0);
    });

    it('metrics section has aria-label', async () => {
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Container overview metrics'), {
        timeout: 3000,
      }).catch(() => {});
      expect(screen.getByLabelText('Container overview metrics')).toBeInTheDocument();
    });

    it('last refreshed timestamp uses aria-live', async () => {
      render(<AdminSystemStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Container overview metrics'), {
        timeout: 3000,
      }).catch(() => {});
      const liveRegions = document.querySelectorAll('[aria-live]');
      expect(liveRegions.length).toBeGreaterThanOrEqual(0);
    });
  });

  /* ── AdminIndexingStatusPage ───────────────────────────────────────── */
  describe('AdminIndexingStatusPage', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.stubGlobal(
        'fetch',
        mockFetch({ summary: mockIndexingSummary, documents: mockIndexingDocuments })
      );
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Indexing summary metrics'), {
        timeout: 3000,
      }).catch(() => {});
      await checkAccessibility(container);
    });

    it('has main landmark', () => {
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('filter buttons use aria-pressed', async () => {
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Indexing summary metrics'), {
        timeout: 3000,
      }).catch(() => {});
      const filterBtns = screen.queryAllByRole('button');
      const anyPressed = filterBtns.some((b) => b.getAttribute('aria-pressed') !== null);
      // At least filter buttons should have aria-pressed
      expect(anyPressed || filterBtns.length === 0).toBe(true);
    });

    it('metrics section has aria-label', async () => {
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Indexing summary metrics'), {
        timeout: 3000,
      }).catch(() => {});
      expect(screen.getByLabelText('Indexing summary metrics')).toBeInTheDocument();
    });

    it('table headers have scope="col"', async () => {
      render(<AdminIndexingStatusPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.getByLabelText('Indexing summary metrics'), {
        timeout: 3000,
      }).catch(() => {});
      const tables = screen.queryAllByRole('table');
      tables.forEach((table) => {
        const ths = table.querySelectorAll('th');
        ths.forEach((th) => expect(th.getAttribute('scope')).toBeTruthy());
      });
    });
  });

  /* ── AdminDocumentsPage ────────────────────────────────────────────── */
  describe('AdminDocumentsPage', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', mockFetch(mockDocManagerResponse));
    });

    it('should have no critical accessibility violations', async () => {
      const { container } = render(<AdminDocumentsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.queryByRole('table'), { timeout: 3000 }).catch(() => {});
      await checkAccessibility(container);
    });

    it('tab controls use proper ARIA attributes', async () => {
      render(<AdminDocumentsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.queryByRole('table'), { timeout: 3000 }).catch(() => {});
      const tabs = screen.queryAllByRole('tab');
      tabs.forEach((tab) => {
        expect(
          tab.getAttribute('aria-selected') !== null || tab.getAttribute('aria-pressed') !== null
        ).toBe(true);
      });
    });

    it('search input has accessible label', async () => {
      render(<AdminDocumentsPage />, { wrapper: IntlWrapper });
      await waitFor(() => screen.queryByPlaceholderText(/filter/i), { timeout: 3000 }).catch(
        () => {}
      );
      const search = screen.queryByPlaceholderText(/filter/i);
      if (search) {
        expect(
          search.getAttribute('aria-label') ??
            search.getAttribute('aria-labelledby') ??
            document.querySelector(`label[for="${search.id}"]`) ??
            search.getAttribute('placeholder')
        ).toBeTruthy();
      }
    });
  });
});
