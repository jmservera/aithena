import { useMemo } from 'react';
import { useIntl } from 'react-intl';
import { RefreshCw, Server, Box, AlertTriangle } from 'lucide-react';
import { useAdminSystemStatus, type ContainerInfo } from '../hooks/useAdminSystemStatus';

/* ── Helpers ──────────────────────────────────────────────────────────── */

function statusEmoji(status: string): string {
  if (status === 'up') return '🟢';
  if (status === 'down') return '🔴';
  return '🟠';
}

function statusLabel(status: string): string {
  if (status === 'up') return 'healthy';
  if (status === 'down') return 'down';
  return 'unknown';
}

/* ── Sub-components ───────────────────────────────────────────────────── */

function ServiceCard({ container }: { container: ContainerInfo }) {
  const intl = useIntl();
  const emoji = statusEmoji(container.status);
  const label = statusLabel(container.status);

  return (
    <div
      className={`system-status-card system-status-card--${label}`}
      aria-label={intl.formatMessage(
        { id: 'systemStatus.serviceCardAria' },
        { name: container.name, status: label }
      )}
    >
      <div className="system-status-card-header">
        <span className="system-status-emoji" aria-hidden="true">
          {emoji}
        </span>
        <span className="system-status-card-name">{container.name}</span>
      </div>
      <div className="system-status-card-details">
        {container.version && (
          <span className="system-status-card-version">
            {intl.formatMessage({ id: 'systemStatus.version' })}: {container.version}
          </span>
        )}
        {container.commit && (
          <span className="system-status-card-commit">
            {intl.formatMessage({ id: 'systemStatus.commit' })}:{' '}
            <code>{container.commit.substring(0, 7)}</code>
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

function AdminSystemStatusPage() {
  const intl = useIntl();
  const { data, loading, error, lastRefreshed, isStale, refresh } = useAdminSystemStatus();

  const fmt = (id: string, values?: Record<string, string | number>) =>
    intl.formatMessage({ id }, values);

  const appServices = useMemo(
    () => data?.containers.filter((c) => c.type === 'service') ?? [],
    [data]
  );

  const infraServices = useMemo(
    () => data?.containers.filter((c) => c.type === 'infrastructure') ?? [],
    [data]
  );

  const needsAttention = data ? data.total - data.healthy : 0;
  const isInitialLoad = loading && !data;

  return (
    <main className="admin-page" aria-label={fmt('systemStatus.pageAria')}>
      <header className="admin-header">
        <h2 className="admin-title">{fmt('adminPages.systemStatus.title')}</h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading}
            aria-label={fmt('systemStatus.refreshAria')}
          >
            <RefreshCw size={14} aria-hidden="true" className={loading ? 'spin' : ''} />
            {fmt('systemStatus.refresh')}
          </button>
          {lastRefreshed && (
            <span
              className={`system-status-last-refreshed ${isStale ? 'system-status-last-refreshed--stale' : ''}`}
              aria-live="polite"
            >
              {isStale && <AlertTriangle size={12} aria-hidden="true" />}
              {fmt('systemStatus.lastRefreshed', {
                time: lastRefreshed.toLocaleTimeString(),
              })}
            </span>
          )}
        </div>
      </header>

      {isInitialLoad && <p className="admin-loading">{fmt('systemStatus.loading')}</p>}

      {error && !data && (
        <div className="admin-error-banner" role="alert">
          {fmt('admin.errorPrefix')} {error}
        </div>
      )}

      {error && data && (
        <div className="admin-error-banner" role="alert">
          {fmt('systemStatus.refreshError', { error })}
        </div>
      )}

      {data && (
        <>
          {/* ── Container Overview Metrics ─────────────────────── */}
          <section className="admin-metrics" aria-label={fmt('systemStatus.metricsAria')}>
            <div className="admin-metric-card">
              <span className="admin-metric-value">{data.total}</span>
              <span className="admin-metric-label">{fmt('systemStatus.metricTotal')}</span>
            </div>
            <div className="admin-metric-card admin-metric-card--processed">
              <span className="admin-metric-value">{data.healthy}</span>
              <span className="admin-metric-label">{fmt('systemStatus.metricHealthy')}</span>
            </div>
            <div
              className={`admin-metric-card ${needsAttention > 0 ? 'admin-metric-card--failed' : 'admin-metric-card--processed'}`}
            >
              <span className="admin-metric-value">{needsAttention}</span>
              <span className="admin-metric-label">{fmt('systemStatus.metricAttention')}</span>
            </div>
          </section>

          {/* ── Application Services ──────────────────────────── */}
          <section aria-label={fmt('systemStatus.appServicesAria')}>
            <h3 className="system-status-section-title">
              <Server size={18} aria-hidden="true" />
              {fmt('systemStatus.appServicesTitle')}
            </h3>
            {appServices.length === 0 ? (
              <p className="admin-empty">{fmt('systemStatus.noServices')}</p>
            ) : (
              <div className="system-status-grid">
                {appServices.map((c) => (
                  <ServiceCard key={c.name} container={c} />
                ))}
              </div>
            )}
          </section>

          {/* ── Infrastructure Services ───────────────────────── */}
          <section aria-label={fmt('systemStatus.infraServicesAria')}>
            <h3 className="system-status-section-title">
              <Box size={18} aria-hidden="true" />
              {fmt('systemStatus.infraServicesTitle')}
            </h3>
            {infraServices.length === 0 ? (
              <p className="admin-empty">{fmt('systemStatus.noServices')}</p>
            ) : (
              <div className="system-status-grid">
                {infraServices.map((c) => (
                  <ServiceCard key={c.name} container={c} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

export default AdminSystemStatusPage;
