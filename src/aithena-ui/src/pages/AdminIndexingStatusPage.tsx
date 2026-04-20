import { useEffect, useMemo } from 'react';
import { useIntl } from 'react-intl';
import {
  useAdminIndexingStatus,
  type IndexingDocument,
  type IndexingDocumentStatus,
} from '../hooks/useAdminIndexingStatus';
import Pagination from '../Components/Pagination';
import './AdminIndexingStatusPage.css';

const PAGE_SIZE = 25;

type StatusFilter = IndexingDocumentStatus | 'all';

const STATUS_FILTERS: { key: StatusFilter; labelId: string }[] = [
  { key: 'all', labelId: 'indexingStatus.filter.all' },
  { key: 'queued', labelId: 'indexingStatus.filter.queued' },
  { key: 'processing', labelId: 'indexingStatus.filter.processing' },
  { key: 'processed', labelId: 'indexingStatus.filter.processed' },
  { key: 'failed', labelId: 'indexingStatus.filter.failed' },
];

function formatTimestamp(ts?: string): string {
  if (!ts) return '\u2014';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function StatusBadge({ status }: { status: IndexingDocumentStatus }) {
  const intl = useIntl();
  return (
    <span className={`status-badge status-badge--${status}`}>
      {intl.formatMessage({ id: `indexingStatus.status.${status}` })}
    </span>
  );
}

function BoolIndicator({ value }: { value: boolean }) {
  return value ? (
    <span className="indexing-status-bool--yes" aria-label="yes">
      ✅
    </span>
  ) : (
    <span className="indexing-status-bool--no" aria-label="no">
      ❌
    </span>
  );
}

function ProgressBar({ done, label }: { done: boolean; label: string }) {
  const pct = done ? 100 : 0;
  return (
    <div className="indexing-status-progress-row">
      <span>{label}</span>
      <div
        className="indexing-status-progress-bar"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={`indexing-status-progress-fill ${done ? 'indexing-status-progress-fill--done' : 'indexing-status-progress-fill--pending'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ProcessingSection({ docs }: { docs: IndexingDocument[] }) {
  const intl = useIntl();

  if (docs.length === 0) return null;

  return (
    <section aria-label={intl.formatMessage({ id: 'indexingStatus.processing.sectionAria' })}>
      <h3 className="indexing-status-section-title">
        {intl.formatMessage({ id: 'indexingStatus.processing.title' })}
      </h3>
      <div className="indexing-status-processing">
        {docs.map((doc) => (
          <div key={doc.id} className="indexing-status-processing-card">
            <div className="indexing-status-processing-card-header">
              <StatusBadge status="processing" />
              <span>{doc.title ?? doc.path}</span>
            </div>
            <div className="indexing-status-processing-card-details">
              <span>
                {intl.formatMessage({ id: 'indexingStatus.col.pageCount' })}: {doc.page_count}
              </span>
              <span>
                {intl.formatMessage({ id: 'indexingStatus.col.chunkCount' })}: {doc.chunk_count}
              </span>
            </div>
            <ProgressBar
              done={doc.text_indexed}
              label={intl.formatMessage({ id: 'indexingStatus.progress.text' })}
            />
            <ProgressBar
              done={doc.embedding_indexed}
              label={intl.formatMessage({ id: 'indexingStatus.progress.embedding' })}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

function DocumentTable({
  docs,
  page,
  onPageChange,
}: {
  docs: IndexingDocument[];
  page: number;
  onPageChange: (p: number) => void;
}) {
  const intl = useIntl();

  if (docs.length === 0) {
    return (
      <p className="admin-empty">{intl.formatMessage({ id: 'indexingStatus.table.empty' })}</p>
    );
  }

  const start = (page - 1) * PAGE_SIZE;
  const pageDocs = docs.slice(start, start + PAGE_SIZE);

  return (
    <>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.status' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.path' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.title' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.textIndexed' })}</th>
              <th scope="col">
                {intl.formatMessage({ id: 'indexingStatus.col.embeddingIndexed' })}
              </th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.pageCount' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.chunkCount' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.error' })}</th>
              <th scope="col">{intl.formatMessage({ id: 'indexingStatus.col.timestamp' })}</th>
            </tr>
          </thead>
          <tbody>
            {pageDocs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <StatusBadge status={doc.status} />
                </td>
                <td>
                  <span className="admin-doc-path">{doc.path}</span>
                </td>
                <td>{doc.title ?? '\u2014'}</td>
                <td>
                  <BoolIndicator value={doc.text_indexed} />
                </td>
                <td>
                  <BoolIndicator value={doc.embedding_indexed} />
                </td>
                <td>{doc.page_count}</td>
                <td>{doc.chunk_count}</td>
                <td>
                  {doc.error ? (
                    <span className="indexing-status-error-text" title={doc.error}>
                      {doc.error_stage ? `[${doc.error_stage}] ` : ''}
                      {doc.error}
                    </span>
                  ) : (
                    '\u2014'
                  )}
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

function AdminIndexingStatusPage() {
  const intl = useIntl();
  const {
    data,
    loading,
    error,
    refresh,
    autoRefresh,
    setAutoRefresh,
    statusFilter,
    setStatusFilter,
    page,
    setPage,
  } = useAdminIndexingStatus();

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filteredDocs = useMemo(() => {
    if (!data) return [];
    if (statusFilter === 'all') return data.documents;
    return data.documents.filter((d) => d.status === statusFilter);
  }, [data, statusFilter]);

  const processingDocs = useMemo(
    () => data?.documents.filter((d) => d.status === 'processing') ?? [],
    [data]
  );

  const isLoading = loading && !data;

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">
          {intl.formatMessage({ id: 'adminPages.indexingStatus.title' })}
        </h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading}
            aria-label={intl.formatMessage({ id: 'indexingStatus.refreshAria' })}
          >
            {intl.formatMessage({ id: 'indexingStatus.refresh' })}
          </button>
          <label className="indexing-status-auto-refresh">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            {intl.formatMessage({ id: 'indexingStatus.autoRefresh' })}
          </label>
        </div>
      </header>

      {isLoading && (
        <p className="admin-loading">{intl.formatMessage({ id: 'indexingStatus.loading' })}</p>
      )}

      {error && !data && (
        <div className="admin-error-banner" role="alert">
          {intl.formatMessage({ id: 'admin.errorPrefix' })} {error}
        </div>
      )}

      {data && (
        <>
          <section
            className="admin-metrics"
            aria-label={intl.formatMessage({ id: 'indexingStatus.metricsAria' })}
          >
            <div className="admin-metric-card">
              <span className="admin-metric-value">{data.summary.total}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.total' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--queued">
              <span className="admin-metric-value">{data.summary.queued}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.queued' })}
              </span>
            </div>
            <div className="admin-metric-card indexing-status-metric-card--processing">
              <span className="admin-metric-value">{data.summary.processing}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.processing' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--processed">
              <span className="admin-metric-value">{data.summary.processed}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.processed' })}
              </span>
            </div>
            <div className="admin-metric-card admin-metric-card--failed">
              <span className="admin-metric-value">{data.summary.failed}</span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.failed' })}
              </span>
            </div>
            <div className="admin-metric-card indexing-status-metric-card--pages">
              <span className="admin-metric-value">
                {data.summary.total_pages.toLocaleString()}
              </span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.totalPages' })}
              </span>
            </div>
            <div className="admin-metric-card indexing-status-metric-card--chunks">
              <span className="admin-metric-value">
                {data.summary.total_chunks.toLocaleString()}
              </span>
              <span className="admin-metric-label">
                {intl.formatMessage({ id: 'indexingStatus.metric.totalChunks' })}
              </span>
            </div>
          </section>

          <ProcessingSection docs={processingDocs} />

          <div className="indexing-status-toolbar">
            <div
              className="indexing-status-filter-group"
              role="group"
              aria-label={intl.formatMessage({ id: 'indexingStatus.filterAria' })}
            >
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={`indexing-status-filter-btn ${statusFilter === f.key ? 'indexing-status-filter-btn--active' : ''}`}
                  onClick={() => setStatusFilter(f.key)}
                  aria-pressed={statusFilter === f.key}
                >
                  {intl.formatMessage({ id: f.labelId })}
                </button>
              ))}
            </div>
          </div>

          <h3 className="indexing-status-section-title">
            {intl.formatMessage({ id: 'indexingStatus.table.title' })}
          </h3>
          <DocumentTable docs={filteredDocs} page={page} onPageChange={setPage} />
        </>
      )}
    </main>
  );
}

export default AdminIndexingStatusPage;
