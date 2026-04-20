import { useIntl } from 'react-intl';
import {
  Activity,
  Clock,
  RefreshCw,
  Server,
  AlertTriangle,
  Inbox,
  FileText,
  Users,
} from 'lucide-react';
import {
  useAdminDashboard,
  type ContainerInfo,
  type InfrastructureStatus,
} from '../hooks/useAdminDashboard';

/* ── Small sub-components ─────────────────────────────────────────────── */

function StatusDot({ status }: { status: string }) {
  const isUp = status === 'up';
  return (
    <span
      className={`dashboard-status-dot ${isUp ? 'dashboard-status-dot--up' : 'dashboard-status-dot--down'}`}
      aria-label={isUp ? 'healthy' : 'unhealthy'}
    />
  );
}

function ServiceRow({ container }: { container: ContainerInfo }) {
  return (
    <tr>
      <td className="dashboard-service-name">
        <StatusDot status={container.status} />
        {container.name}
      </td>
      <td>{container.type}</td>
      <td>
        <span
          className={`dashboard-badge ${container.status === 'up' ? 'dashboard-badge--up' : 'dashboard-badge--down'}`}
        >
          {container.status}
        </span>
      </td>
      <td className="dashboard-version">{container.version ?? '\u2014'}</td>
    </tr>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

function AdminDashboardPage() {
  const intl = useIntl();
  const {
    documents,
    queue,
    infrastructure,
    loading,
    errors,
    autoRefresh,
    lastRefreshed,
    refresh,
    toggleAutoRefresh,
  } = useAdminDashboard();

  const fmt = (id: string, values?: Record<string, string | number>) =>
    intl.formatMessage({ id }, values);

  const isInitialLoad = loading && !documents && !queue && !infrastructure;

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">{fmt('dashboard.title')}</h2>
        <div className="admin-actions dashboard-actions">
          <label className="dashboard-auto-refresh">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={toggleAutoRefresh}
              aria-label={fmt('dashboard.autoRefreshLabel')}
            />
            {fmt('dashboard.autoRefresh')}
          </label>
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading}
            aria-label={fmt('dashboard.refreshLabel')}
          >
            <RefreshCw size={14} aria-hidden="true" className={loading ? 'spin' : ''} />
            {fmt('dashboard.refresh')}
          </button>
          {lastRefreshed && (
            <span className="dashboard-last-refreshed" aria-live="polite">
              {fmt('dashboard.lastRefreshed', {
                time: lastRefreshed.toLocaleTimeString(),
              })}
            </span>
          )}
        </div>
      </header>

      {isInitialLoad && <p className="admin-loading">{fmt('dashboard.loading')}</p>}

      <div className="dashboard-grid">
        {/* ── Document Metrics ─────────────────────────────────── */}
        <section className="dashboard-card" aria-label={fmt('dashboard.documentsAria')}>
          <h3 className="dashboard-card-title">
            <FileText size={18} aria-hidden="true" />
            {fmt('dashboard.documentsTitle')}
          </h3>
          {errors.documents && (
            <div className="admin-error-banner" role="alert">
              {fmt('admin.errorPrefix')} {errors.documents}
            </div>
          )}
          {documents && (
            <div className="admin-metrics" aria-label={fmt('dashboard.documentsAria')}>
              <div className="admin-metric-card">
                <span className="admin-metric-value">{documents.total}</span>
                <span className="admin-metric-label">{fmt('admin.metricTotal')}</span>
              </div>
              <div className="admin-metric-card admin-metric-card--queued">
                <span className="admin-metric-value">{documents.queued}</span>
                <span className="admin-metric-label">{fmt('admin.metricQueued')}</span>
              </div>
              <div className="admin-metric-card admin-metric-card--processed">
                <span className="admin-metric-value">{documents.processed}</span>
                <span className="admin-metric-label">{fmt('admin.metricProcessed')}</span>
              </div>
              <div className="admin-metric-card admin-metric-card--failed">
                <span className="admin-metric-value">{documents.failed}</span>
                <span className="admin-metric-label">{fmt('admin.metricFailed')}</span>
              </div>
            </div>
          )}
        </section>

        {/* ── Queue Metrics ───────────────────────────────────── */}
        <section className="dashboard-card" aria-label={fmt('dashboard.queueAria')}>
          <h3 className="dashboard-card-title">
            <Inbox size={18} aria-hidden="true" />
            {fmt('dashboard.queueTitle')}
          </h3>
          {errors.queue && (
            <div className="admin-error-banner" role="alert">
              {fmt('admin.errorPrefix')} {errors.queue}
            </div>
          )}
          {queue && (
            <>
              <div className="admin-metrics" aria-label={fmt('dashboard.queueAria')}>
                <div className="admin-metric-card">
                  <span className="admin-metric-value">{queue.messages_ready}</span>
                  <span className="admin-metric-label">{fmt('dashboard.queueReady')}</span>
                </div>
                <div className="admin-metric-card admin-metric-card--queued">
                  <span className="admin-metric-value">{queue.messages_unacknowledged}</span>
                  <span className="admin-metric-label">{fmt('dashboard.queueUnacked')}</span>
                </div>
                <div className="admin-metric-card">
                  <span className="admin-metric-value">{queue.messages_total}</span>
                  <span className="admin-metric-label">{fmt('dashboard.queueTotal')}</span>
                </div>
              </div>
              <div className="dashboard-queue-meta">
                <span>
                  <Clock size={12} aria-hidden="true" /> {fmt('dashboard.queueName')}:{' '}
                  <code>{queue.queue_name}</code>
                </span>
                <span>
                  <Users size={12} aria-hidden="true" /> {fmt('dashboard.consumers')}:{' '}
                  <strong>{queue.consumers}</strong>
                </span>
              </div>
            </>
          )}
        </section>

        {/* ── Infrastructure Status ───────────────────────────── */}
        <section
          className="dashboard-card dashboard-card--wide"
          aria-label={fmt('dashboard.infraAria')}
        >
          <h3 className="dashboard-card-title">
            <Server size={18} aria-hidden="true" />
            {fmt('dashboard.infraTitle')}
          </h3>
          {errors.infrastructure && (
            <div className="admin-error-banner" role="alert">
              {fmt('admin.errorPrefix')} {errors.infrastructure}
            </div>
          )}
          {infrastructure && <InfraOverview infra={infrastructure} />}
        </section>
      </div>
    </main>
  );
}

function InfraOverview({ infra }: { infra: InfrastructureStatus }) {
  const intl = useIntl();
  const fmt = (id: string, values?: Record<string, string | number>) =>
    intl.formatMessage({ id }, values);

  return (
    <>
      <div className="dashboard-infra-summary">
        <div className="dashboard-infra-stat">
          <Activity size={16} aria-hidden="true" />
          <span>
            {fmt('dashboard.infraHealthy', {
              healthy: infra.healthy,
              total: infra.total,
            })}
          </span>
        </div>
        {infra.healthy < infra.total && (
          <div className="dashboard-infra-stat dashboard-infra-stat--warn">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>
              {fmt('dashboard.infraDegraded', {
                count: infra.total - infra.healthy,
              })}
            </span>
          </div>
        )}
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th scope="col">{fmt('dashboard.infraColService')}</th>
              <th scope="col">{fmt('dashboard.infraColType')}</th>
              <th scope="col">{fmt('dashboard.infraColStatus')}</th>
              <th scope="col">{fmt('dashboard.infraColVersion')}</th>
            </tr>
          </thead>
          <tbody>
            {infra.containers.map((c) => (
              <ServiceRow key={c.name} container={c} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default AdminDashboardPage;
