import { useRef, useEffect, useMemo } from 'react';
import { useIntl } from 'react-intl';
import { RefreshCw, Search, Terminal, AlertCircle, Info } from 'lucide-react';
import { useAdminLogs, TAIL_OPTIONS, INTERVAL_OPTIONS } from '../hooks/useAdminLogs';

function AdminLogsPage() {
  const intl = useIntl();
  const fmt = (id: string, values?: Record<string, string | number>) =>
    intl.formatMessage({ id }, values);

  const {
    services,
    selectedService,
    tailLines,
    logLines,
    loading,
    servicesLoading,
    error,
    servicesError,
    autoRefresh,
    refreshInterval,
    searchFilter,
    setSelectedService,
    setTailLines,
    setAutoRefresh,
    setRefreshInterval,
    setSearchFilter,
    refresh,
  } = useAdminLogs();

  const logEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new logs arrive
  useEffect(() => {
    logEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [logLines]);

  const filteredLines = useMemo(() => {
    if (!searchFilter.trim()) return logLines;
    const lower = searchFilter.toLowerCase();
    return logLines.filter((line) => line.toLowerCase().includes(lower));
  }, [logLines, searchFilter]);

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">
          <Terminal size={20} aria-hidden="true" />
          {fmt('logs.title')}
        </h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading || !selectedService}
            aria-label={fmt('logs.refreshLabel')}
          >
            <RefreshCw size={14} aria-hidden="true" className={loading ? 'spin' : ''} />
            {fmt('logs.refresh')}
          </button>
        </div>
      </header>

      {/* ── Controls ─────────────────────────────────────────── */}
      <div className="logs-controls">
        <div className="logs-control-group">
          <label htmlFor="logs-service-select" className="logs-label">
            {fmt('logs.serviceLabel')}
          </label>
          <select
            id="logs-service-select"
            className="logs-select"
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            disabled={servicesLoading}
            aria-label={fmt('logs.serviceLabel')}
          >
            <option value="">{fmt('logs.selectService')}</option>
            {services.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div className="logs-control-group">
          <label htmlFor="logs-tail-select" className="logs-label">
            {fmt('logs.tailLabel')}
          </label>
          <select
            id="logs-tail-select"
            className="logs-select"
            value={tailLines}
            onChange={(e) => setTailLines(Number(e.target.value))}
            aria-label={fmt('logs.tailLabel')}
          >
            {TAIL_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {fmt('logs.tailOption', { n })}
              </option>
            ))}
          </select>
        </div>

        <div className="logs-control-group logs-control-group--auto-refresh">
          <label className="logs-auto-refresh-label">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              aria-label={fmt('logs.autoRefreshLabel')}
            />
            {fmt('logs.autoRefresh')}
          </label>
          {autoRefresh && (
            <select
              className="logs-select logs-select--small"
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              aria-label={fmt('logs.intervalLabel')}
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="logs-control-group logs-control-group--search">
          <Search size={14} aria-hidden="true" className="logs-search-icon" />
          <input
            type="text"
            className="logs-search-input"
            placeholder={fmt('logs.searchPlaceholder')}
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            aria-label={fmt('logs.searchLabel')}
          />
        </div>
      </div>

      {/* ── Error / Info banners ─────────────────────────────── */}
      {servicesError && (
        <div className="admin-error-banner" role="alert">
          <AlertCircle size={14} aria-hidden="true" />
          {fmt('logs.servicesError', { detail: servicesError })}
        </div>
      )}

      {error && (
        <div className="admin-error-banner" role="alert">
          <AlertCircle size={14} aria-hidden="true" />
          {fmt('logs.fetchError', { detail: error })}
        </div>
      )}

      {!selectedService && !servicesError && (
        <div className="logs-info-banner" role="status">
          <Info size={14} aria-hidden="true" />
          {fmt('logs.selectServiceHint')}
        </div>
      )}

      {/* ── Log output ───────────────────────────────────────── */}
      {selectedService && (
        <div className="logs-output-container">
          {loading && logLines.length === 0 && (
            <p className="admin-loading">{fmt('logs.loading')}</p>
          )}
          <pre className="logs-output" aria-label={fmt('logs.outputLabel')}>
            <code>
              {filteredLines.map((line, i) => (
                <span key={i} className="logs-line">
                  {line}
                  {'\n'}
                </span>
              ))}
            </code>
            <div ref={logEndRef} />
          </pre>
          {searchFilter && (
            <div className="logs-filter-status" aria-live="polite">
              {fmt('logs.filterStatus', {
                shown: filteredLines.length,
                total: logLines.length,
              })}
            </div>
          )}
        </div>
      )}
    </main>
  );
}

export default AdminLogsPage;
