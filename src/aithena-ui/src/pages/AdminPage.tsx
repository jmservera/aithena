import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useAdmin, AdminDocument } from '../hooks/admin';

type TabKey = 'queued' | 'processed' | 'failed';

const ADMIN_TABS: { key: TabKey; getLabel: (counts: Record<TabKey, number>) => string }[] = [
  { key: 'queued', getLabel: (counts) => `⏳ Queued (${counts.queued})` },
  { key: 'processed', getLabel: (counts) => `✅ Processed (${counts.processed})` },
  { key: 'failed', getLabel: (counts) => `❌ Failed (${counts.failed})` },
];

function formatTimestamp(ts?: string): string {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function DocPath({ path }: { path?: string }) {
  return <span className="admin-doc-path">{path ?? '—'}</span>;
}

interface QueuedTableProps {
  docs: AdminDocument[];
}

function QueuedTable({ docs }: QueuedTableProps) {
  if (docs.length === 0) {
    return <p className="admin-empty">No documents currently queued. ✓</p>;
  }

  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Path</th>
            <th>Queued at</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
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
  );
}

interface ProcessedTableProps {
  docs: AdminDocument[];
  onClearAll: () => void;
  busy: boolean;
}

function ProcessedTable({ docs, onClearAll, busy }: ProcessedTableProps) {
  const [confirmClear, setConfirmClear] = useState(false);

  if (docs.length === 0) {
    return <p className="admin-empty">No processed documents yet.</p>;
  }

  return (
    <>
      <div className="admin-doc-toolbar">
        <span className="admin-doc-toolbar-spacer" />
        {confirmClear ? (
          <>
            <span style={{ fontSize: '0.85em', color: '#fca5a5' }}>
              Clear {docs.length} processed document(s)?
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
              ✅ Confirm
            </button>
            <button
              type="button"
              className="admin-btn"
              onClick={() => setConfirmClear(false)}
              disabled={busy}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className="admin-btn admin-btn--danger"
            onClick={() => setConfirmClear(true)}
            disabled={busy}
          >
            🗑️ Clear All
          </button>
        )}
      </div>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Path</th>
              <th>Title</th>
              <th>Author</th>
              <th>Year</th>
              <th>Indexed at</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>{doc.title ?? '—'}</td>
                <td>{doc.author ?? '—'}</td>
                <td>{doc.year ?? '—'}</td>
                <td>{formatTimestamp(doc.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

interface FailedTableProps {
  docs: AdminDocument[];
  onRequeue: (id: string) => void;
  onRequeueAll: () => void;
  busy: boolean;
}

function FailedTable({ docs, onRequeue, onRequeueAll, busy }: FailedTableProps) {
  if (docs.length === 0) {
    return <p className="admin-empty">No failed documents. 🎉</p>;
  }

  return (
    <>
      <div className="admin-doc-toolbar">
        <span className="admin-doc-toolbar-spacer" />
        <button
          type="button"
          className="admin-btn admin-btn--primary"
          onClick={onRequeueAll}
          disabled={busy}
        >
          🔄 Requeue All ({docs.length})
        </button>
      </div>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Path</th>
              <th>Error</th>
              <th>Failed at</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>
                  <span className="admin-doc-error">
                    {doc.error ?? 'No error details recorded.'}
                  </span>
                </td>
                <td>{formatTimestamp(doc.timestamp)}</td>
                <td>
                  <button
                    type="button"
                    className="admin-btn"
                    onClick={() => onRequeue(doc.id)}
                    disabled={busy}
                  >
                    🔄 Requeue
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function AdminPage() {
  const { data, loading, error, refresh, requeueDocument, requeueAllFailed, clearProcessed } =
    useAdmin();
  const [activeTab, setActiveTab] = useState<TabKey>('queued');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const tabRefs = useRef<Record<TabKey, HTMLButtonElement | null>>({
    queued: null,
    processed: null,
    failed: null,
  });

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  }

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
    () => data?.documents.filter((document) => document.status === 'queued') ?? [],
    [data]
  );
  const processedDocs = useMemo(
    () => data?.documents.filter((document) => document.status === 'processed') ?? [],
    [data]
  );
  const failedDocs = useMemo(
    () => data?.documents.filter((document) => document.status === 'failed') ?? [],
    [data]
  );

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex: number | null = null;

    switch (event.key) {
      case 'ArrowRight':
        nextIndex = (currentIndex + 1) % ADMIN_TABS.length;
        break;
      case 'ArrowLeft':
        nextIndex = (currentIndex - 1 + ADMIN_TABS.length) % ADMIN_TABS.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = ADMIN_TABS.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const nextTab = ADMIN_TABS[nextIndex].key;
    setActiveTab(nextTab);
    tabRefs.current[nextTab]?.focus();
  };

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">🏛️ Admin Dashboard</h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={() => runAction(refresh)}
            disabled={loading || busy}
          >
            🔄 Refresh
          </button>
        </div>
      </header>

      {isLoading && <p className="admin-loading">Loading queue state…</p>}

      {error && !data && (
        <div className="admin-error-banner" role="alert">
          ⚠ {error}
        </div>
      )}

      {actionError && (
        <div className="admin-error-banner" role="alert">
          ⚠ {actionError}
        </div>
      )}

      {data && (
        <>
          <section className="admin-metrics" aria-label="Queue metrics">
            <div className="admin-metric-card">
              <span className="admin-metric-value">{data.total}</span>
              <span className="admin-metric-label">Total</span>
            </div>
            <div className="admin-metric-card admin-metric-card--queued">
              <span className="admin-metric-value">{data.queued}</span>
              <span className="admin-metric-label">Queued</span>
            </div>
            <div className="admin-metric-card admin-metric-card--processed">
              <span className="admin-metric-value">{data.processed}</span>
              <span className="admin-metric-label">Processed</span>
            </div>
            <div className="admin-metric-card admin-metric-card--failed">
              <span className="admin-metric-value">{data.failed}</span>
              <span className="admin-metric-label">Failed</span>
            </div>
          </section>

          <div
            className="admin-tabs"
            role="tablist"
            aria-label="Document status tabs"
            aria-orientation="horizontal"
          >
            {ADMIN_TABS.map((tab, index) => {
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
                  {tab.getLabel(counts)}
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
              <QueuedTable docs={queuedDocs} />
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
                busy={busy}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}

export default AdminPage;
