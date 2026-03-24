import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { Database, Rabbit, ExternalLink } from 'lucide-react';
import { useAdmin, AdminDocument } from '../hooks/admin';

type TabKey = 'queued' | 'processed' | 'failed';

const ADMIN_TABS: { key: TabKey; labelId: string }[] = [
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

interface QueuedTableProps {
  docs: AdminDocument[];
}

function QueuedTable({ docs }: QueuedTableProps) {
  const intl = useIntl();
  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.queued.empty' })}</p>;
  }

  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th scope="col">{intl.formatMessage({ id: 'admin.queued.headerPath' })}</th>
            <th scope="col">{intl.formatMessage({ id: 'admin.queued.headerQueuedAt' })}</th>
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
  const intl = useIntl();
  const [confirmClear, setConfirmClear] = useState(false);

  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.processed.empty' })}</p>;
  }

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
              <th scope="col">{intl.formatMessage({ id: 'admin.processed.headerIndexedAt' })}</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>{doc.title ?? '\u2014'}</td>
                <td>{doc.author ?? '\u2014'}</td>
                <td>{doc.year ?? '\u2014'}</td>
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
  const intl = useIntl();
  if (docs.length === 0) {
    return <p className="admin-empty">{intl.formatMessage({ id: 'admin.failed.empty' })}</p>;
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
          {intl.formatMessage({ id: 'admin.failed.requeueAll' }, { count: docs.length })}
        </button>
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
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <DocPath path={doc.path} />
                </td>
                <td>
                  <span className="admin-doc-error">
                    {doc.error ?? intl.formatMessage({ id: 'admin.failed.noError' })}
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
                    {intl.formatMessage({ id: 'admin.failed.requeue' })}
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

const INFRA_LINKS = [
  {
    labelId: 'admin.infra.solr',
    descriptionId: 'admin.infra.solrDescription',
    href: '/admin/solr/',
    Icon: Database,
  },
  {
    labelId: 'admin.infra.rabbitmq',
    descriptionId: 'admin.infra.rabbitmqDescription',
    href: '/admin/rabbitmq/',
    Icon: Rabbit,
  },
];

function InfrastructureLinks() {
  const intl = useIntl();
  return (
    <section
      className="admin-infra"
      aria-label={intl.formatMessage({ id: 'admin.infra.sectionAria' })}
    >
      <h3 className="admin-infra-heading">{intl.formatMessage({ id: 'admin.infra.heading' })}</h3>
      <div className="admin-infra-cards">
        {INFRA_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="admin-infra-card"
          >
            <link.Icon size={24} aria-hidden="true" />
            <div className="admin-infra-card-text">
              <span className="admin-infra-card-label">
                {intl.formatMessage({ id: link.labelId })}
              </span>
              <span className="admin-infra-card-desc">
                {intl.formatMessage({ id: link.descriptionId })}
              </span>
            </div>
            <ExternalLink size={14} aria-hidden="true" className="admin-infra-card-ext" />
          </a>
        ))}
      </div>
    </section>
  );
}

function AdminPage() {
  const intl = useIntl();
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
      setActionError(
        err instanceof Error ? err.message : intl.formatMessage({ id: 'admin.actionFailed' })
      );
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
    let nextIndex: number;

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
        <h2 className="admin-title">{intl.formatMessage({ id: 'admin.title' })}</h2>
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

          <InfrastructureLinks />

          <div
            className="admin-tabs"
            role="tablist"
            aria-label={intl.formatMessage({ id: 'admin.tabsAria' })}
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
