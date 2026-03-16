import { useEffect, useState } from 'react';
import { useAdmin, AdminDocument } from '../hooks/admin';

type TabKey = 'queued' | 'processed' | 'failed';

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
              className="admin-btn admin-btn--danger"
              onClick={() => {
                setConfirmClear(false);
                onClearAll();
              }}
              disabled={busy}
            >
              ✅ Confirm
            </button>
            <button className="admin-btn" onClick={() => setConfirmClear(false)} disabled={busy}>
              Cancel
            </button>
          </>
        ) : (
          <button
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
        <button className="admin-btn admin-btn--primary" onClick={onRequeueAll} disabled={busy}>
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
                  <button className="admin-btn" onClick={() => onRequeue(doc.id)} disabled={busy}>
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

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">🏛️ Admin Dashboard</h2>
        <div className="admin-actions">
          <button
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

          <div className="admin-tabs" role="tablist">
            {(['queued', 'processed', 'failed'] as TabKey[]).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                className={`admin-tab-btn ${activeTab === tab ? 'admin-tab-btn--active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab === 'queued' && `⏳ Queued (${data.queued})`}
                {tab === 'processed' && `✅ Processed (${data.processed})`}
                {tab === 'failed' && `❌ Failed (${data.failed})`}
              </button>
            ))}
          </div>

          {activeTab === 'queued' && (
            <QueuedTable docs={data.documents.filter((d) => d.status === 'queued')} />
          )}

          {activeTab === 'processed' && (
            <ProcessedTable
              docs={data.documents.filter((d) => d.status === 'processed')}
              onClearAll={() => runAction(clearProcessed)}
              busy={busy}
            />
          )}

          {activeTab === 'failed' && (
            <FailedTable
              docs={data.documents.filter((d) => d.status === 'failed')}
              onRequeue={(id) => runAction(() => requeueDocument(id))}
              onRequeueAll={() => runAction(requeueAllFailed)}
              busy={busy}
            />
          )}
        </>
      )}
    </main>
  );
}

export default AdminPage;
