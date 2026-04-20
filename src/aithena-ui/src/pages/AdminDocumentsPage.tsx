import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { Search } from 'lucide-react';
import { useAdmin, AdminDocument } from '../hooks/admin';
import Pagination from '../Components/Pagination';

type TabKey = 'queued' | 'processed' | 'failed';

const PAGE_SIZE = 25;

const TABS: { key: TabKey; labelId: string }[] = [
  { key: 'queued', labelId: 'admin.tab.queued' },
  { key: 'processed', labelId: 'admin.tab.processed' },
  { key: 'failed', labelId: 'admin.tab.failed' },
];

function formatTimestamp(ts?: string): string {
  if (!ts) return '\u2014';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function DocPath({ path }: { path?: string }) {
  return <span className="admin-doc-path">{path ?? '\u2014'}</span>;
}

/* ── Queued table ─────────────────────────────────────────────── */

interface QueuedTableProps {
  docs: AdminDocument[];
  page: number;
  onPageChange: (page: number) => void;
}

function QueuedTable({ docs, page, onPageChange }: QueuedTableProps) {
  const intl = useIntl();
  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.queued.empty' })}</p>;
  }

  const start = (page - 1) * PAGE_SIZE;
  const pageDocs = docs.slice(start, start + PAGE_SIZE);

  return (
    <>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th scope="col">{intl.formatMessage({ id: 'admin.queued.headerPath' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.queued.headerQueuedAt' })}</th>
            </tr>
          </thead>
          <tbody>
            {pageDocs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>{formatTimestamp(doc.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} limit={PAGE_SIZE} total={docs.length} onPageChange={onPageChange} />
    </>
  );
}

/* ── Processed table ──────────────────────────────────────────── */

interface ProcessedTableProps {
  docs: AdminDocument[];
  onClearAll: () => void;
  busy: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

function ProcessedTable({ docs, onClearAll, busy, page, onPageChange }: ProcessedTableProps) {
  const intl = useIntl();
  const [confirmClear, setConfirmClear] = useState(false);

  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.processed.empty' })}</p>;
  }

  const start = (page - 1) * PAGE_SIZE;
  const pageDocs = docs.slice(start, start + PAGE_SIZE);

  return (
    <>
      <div className="admin-doc-toolbar">
        <span className="admin-doc-toolbar-spacer" />
        {confirmClear ? (
          <>
            <span style={{ fontSize: '0.85em', color: '#fca5a5' }}>
              {intl.formatMessage({ id: 'admin.processed.clearConfirm' }, { count: docs.length })}
            </span>
            <button
              type="button"
              className="admin-btn admin-btn--danger"
              onClick={() => {
                setConfirmClear(false);
                onClearAll();
              }}
              disabled={busy}
            >
              {intl.formatMessage({ id: 'admin.processed.confirm' })}
            </button>
            <button
              type="button"
              className="admin-btn"
              onClick={() => setConfirmClear(false)}
              disabled={busy}
            >
              {intl.formatMessage({ id: 'admin.processed.cancel' })}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="admin-btn admin-btn--danger"
            onClick={() => setConfirmClear(true)}
            disabled={busy}
          >
            {intl.formatMessage({ id: 'admin.processed.clearAll' })}
          </button>
        )}
      </div>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerPath' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerTitle' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerAuthor' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerYear' })}</th>
              <th scope="col">
                {intl.formatMessage({ id: 'adminDocs.processed.headerPageCount' })}
              </th>
              <th scope="col">
                {intl.formatMessage({ id: 'adminDocs.processed.headerChunkCount' })}
              </th>
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerIndexedAt' })}</th>
            </tr>
          </thead>
          <tbody>
            {pageDocs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>{doc.title ?? '\u2014'}</td>
                <td>{doc.author ?? '\u2014'}</td>
                <td>{doc.year ?? '\u2014'}</td>
                <td>{doc.page_count ?? '\u2014'}</td>
                <td>{doc.chunk_count ?? '\u2014'}</td>
                <td>{formatTimestamp(doc.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} limit={PAGE_SIZE} total={docs.length} onPageChange={onPageChange} />
    </>
  );
}

/* ── Failed table ─────────────────────────────────────────────── */

interface FailedTableProps {
  docs: AdminDocument[];
  onRequeue: (id: string) => void;
  onRequeueAll: () => void;
  onDelete: (id: string) => void;
  busy: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

function FailedTable({
  docs,
  onRequeue,
  onRequeueAll,
  onDelete,
  busy,
  page,
  onPageChange,
}: FailedTableProps) {
  const intl = useIntl();
  const [confirmRequeueAll, setConfirmRequeueAll] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.failed.empty' })}</p>;
  }

  const start = (page - 1) * PAGE_SIZE;
  const pageDocs = docs.slice(start, start + PAGE_SIZE);

  return (
    <>
      <div className="admin-doc-toolbar">
        <span className="admin-doc-toolbar-spacer" />
        {confirmRequeueAll ? (
          <>
            <span style={{ fontSize: '0.85em', color: '#fca5a5' }}>
              {intl.formatMessage(
                { id: 'adminDocs.failed.requeueConfirm' },
                { count: docs.length }
              )}
            </span>
            <button
              type="button"
              className="admin-btn admin-btn--primary"
              onClick={() => {
                setConfirmRequeueAll(false);
                onRequeueAll();
              }}
              disabled={busy}
            >
              {intl.formatMessage({ id: 'admin.processed.confirm' })}
            </button>
            <button
              type="button"
              className="admin-btn"
              onClick={() => setConfirmRequeueAll(false)}
              disabled={busy}
            >
              {intl.formatMessage({ id: 'admin.processed.cancel' })}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            onClick={() => setConfirmRequeueAll(true)}
            disabled={busy}
          >
            {intl.formatMessage({ id: 'admin.failed.requeueAll' }, { count: docs.length })}
          </button>
        )}
      </div>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th scope="col">{intl.formatMessage({ id: 'admin.failed.headerPath' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.failed.headerError' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.failed.headerFailedAt' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'admin.failed.headerAction' })}</th>
            </tr>
          </thead>
          <tbody>
            {pageDocs.map((doc) => {
              const isExpanded = expandedId === doc.id;
              return (
                <>
                  <tr key={doc.id}>
                    <td>
                      <DocPath path={doc.path} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="admin-doc-error-toggle"
                        onClick={() => setExpandedId(isExpanded ? null : doc.id)}
                        aria-expanded={isExpanded}
                        aria-controls={`error-detail-${doc.id}`}
                      >
                        {doc.error
                          ? doc.error.length > 60
                            ? `${doc.error.slice(0, 60)}…`
                            : doc.error
                          : intl.formatMessage({ id: 'admin.failed.noError' })}
                      </button>
                    </td>
                    <td>{formatTimestamp(doc.timestamp)}</td>
                    <td className="admin-doc-actions">
                      <button
                        type="button"
                        className="admin-btn"
                        onClick={() => onRequeue(doc.id)}
                        disabled={busy}
                      >
                        {intl.formatMessage({ id: 'admin.failed.requeue' })}
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--danger"
                        onClick={() => onDelete(doc.id)}
                        disabled={busy}
                        aria-label={intl.formatMessage(
                          { id: 'adminDocs.failed.deleteAria' },
                          { path: doc.path ?? doc.id }
                        )}
                      >
                        {intl.formatMessage({ id: 'adminDocs.failed.delete' })}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${doc.id}-detail`}>
                      <td colSpan={4}>
                        <div
                          id={`error-detail-${doc.id}`}
                          className="admin-doc-error-detail"
                          role="region"
                          aria-label={intl.formatMessage({
                            id: 'adminDocs.failed.errorDetailAria',
                          })}
                        >
                          <pre>
                            {doc.error ?? intl.formatMessage({ id: 'admin.failed.noError' })}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pagination page={page} limit={PAGE_SIZE} total={docs.length} onPageChange={onPageChange} />
    </>
  );
}

/* ── Main page ────────────────────────────────────────────────── */

function AdminDocumentsPage() {
  const intl = useIntl();
  const {
    data,
    loading,
    error,
    refresh,
    requeueDocument,
    requeueAllFailed,
    clearProcessed,
    deleteDocument,
  } = useAdmin();
  const [activeTab, setActiveTab] = useState<TabKey>('queued');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [pages, setPages] = useState<Record<TabKey, number>>({
    queued: 1,
    processed: 1,
    failed: 1,
  });
  const tabRefs = useRef<Record<TabKey, HTMLButtonElement | null>>({
    queued: null,
    processed: null,
    failed: null,
  });

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setTabPage = (tab: TabKey, page: number) => setPages((prev) => ({ ...prev, [tab]: page }));

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : intl.formatMessage({ id: 'admin.actionFailed' })
      );
    } finally {
      setBusy(false);
    }
  }

  const filterByPath = (docs: AdminDocument[]) => {
    if (!searchQuery.trim()) return docs;
    const query = searchQuery.toLowerCase();
    return docs.filter((doc) => doc.path?.toLowerCase().includes(query));
  };

  const isLoading = loading && !data;
  const counts = useMemo<Record<TabKey, number>>(
    () => ({
      queued: data?.queued ?? 0,
      processed: data?.processed ?? 0,
      failed: data?.failed ?? 0,
    }),
    [data]
  );
  const queuedDocs = useMemo(
    () => filterByPath(data?.documents.filter((d) => d.status === 'queued') ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, searchQuery]
  );
  const processedDocs = useMemo(
    () => filterByPath(data?.documents.filter((d) => d.status === 'processed') ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, searchQuery]
  );
  const failedDocs = useMemo(
    () => filterByPath(data?.documents.filter((d) => d.status === 'failed') ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, searchQuery]
  );

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPages({ queued: 1, processed: 1, failed: 1 });
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex: number;

    switch (event.key) {
      case 'ArrowRight':
        nextIndex = (currentIndex + 1) % TABS.length;
        break;
      case 'ArrowLeft':
        nextIndex = (currentIndex - 1 + TABS.length) % TABS.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = TABS.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const nextTab = TABS[nextIndex].key;
    setActiveTab(nextTab);
    tabRefs.current[nextTab]?.focus();
  };

  return (
    <main className="admin-page" aria-labelledby="admin-docs-heading">
      <header className="admin-header">
        <h2 id="admin-docs-heading" className="admin-title">
          {intl.formatMessage({ id: 'adminDocs.title' })}
        </h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={() => runAction(refresh)}
            disabled={loading || busy}
          >
            {intl.formatMessage({ id: 'admin.refresh' })}
          </button>
        </div>
      </header>

      {isLoading && <p className="admin-loading">{intl.formatMessage({ id: 'admin.loading' })}</p>}

      {error && !data && (
        <div className="admin-error-banner" role="alert">
          {intl.formatMessage({ id: 'admin.errorPrefix' })} {error}
        </div>
      )}

      {actionError && (
        <div className="admin-error-banner" role="alert">
          {intl.formatMessage({ id: 'admin.errorPrefix' })} {actionError}
        </div>
      )}

      {data && (
        <>
          <section
            className="admin-metrics"
            aria-label={intl.formatMessage({ id: 'admin.metricsAria' })}
          >
            <div className="admin-metric-card">
              <span className="admin-metric-value">{data.total}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'admin.metricTotal' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--queued">
              <span className="admin-metric-value">{data.queued}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'admin.metricQueued' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--processed">
              <span className="admin-metric-value">{data.processed}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'admin.metricProcessed' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--failed">
              <span className="admin-metric-value">{data.failed}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'admin.metricFailed' })}
              </span>
            </div>
          </section>

          <div className="admin-search" role="search">
            <label htmlFor="admin-doc-search" className="admin-search-label">
              <Search size={16} aria-hidden="true" />
              <span className="sr-only">{intl.formatMessage({ id: 'adminDocs.searchLabel' })}</span>
            </label>
            <input
              id="admin-doc-search"
              type="search"
              className="admin-search-input"
              placeholder={intl.formatMessage({ id: 'adminDocs.searchPlaceholder' })}
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </div>

          <div
            className="admin-tabs"
            role="tablist"
            aria-label={intl.formatMessage({ id: 'admin.tabsAria' })}
            aria-orientation="horizontal"
          >
            {TABS.map((tab, index) => {
              const tabId = `admin-tab-${tab.key}`;
              const panelId = `admin-panel-${tab.key}`;
              const isActive = activeTab === tab.key;

              return (
                <button
                  key={tab.key}
                  id={tabId}
                  ref={(node) => {
                    tabRefs.current[tab.key] = node;
                  }}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={panelId}
                  tabIndex={isActive ? 0 : -1}
                  className={`admin-tab-btn ${isActive ? 'admin-tab-btn--active' : ''}`}
                  onClick={() => setActiveTab(tab.key)}
                  onKeyDown={(event) => handleTabKeyDown(event, index)}
                >
                  {intl.formatMessage({ id: tab.labelId }, { count: counts[tab.key] })}
                </button>
              );
            })}
          </div>

          {activeTab === 'queued' && (
            <section
              id="admin-panel-queued"
              className="admin-tab-panel"
              role="tabpanel"
              aria-labelledby="admin-tab-queued"
              tabIndex={0}
            >
              <QueuedTable
                docs={queuedDocs}
                page={pages.queued}
                onPageChange={(p) => setTabPage('queued', p)}
              />
            </section>
          )}

          {activeTab === 'processed' && (
            <section
              id="admin-panel-processed"
              className="admin-tab-panel"
              role="tabpanel"
              aria-labelledby="admin-tab-processed"
              tabIndex={0}
            >
              <ProcessedTable
                docs={processedDocs}
                onClearAll={() => runAction(clearProcessed)}
                busy={busy}
                page={pages.processed}
                onPageChange={(p) => setTabPage('processed', p)}
              />
            </section>
          )}

          {activeTab === 'failed' && (
            <section
              id="admin-panel-failed"
              className="admin-tab-panel"
              role="tabpanel"
              aria-labelledby="admin-tab-failed"
              tabIndex={0}
            >
              <FailedTable
                docs={failedDocs}
                onRequeue={(id) => runAction(() => requeueDocument(id))}
                onRequeueAll={() => runAction(requeueAllFailed)}
                onDelete={(id) => runAction(() => deleteDocument(id))}
                busy={busy}
                page={pages.failed}
                onPageChange={(p) => setTabPage('failed', p)}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}

export default AdminDocumentsPage;
