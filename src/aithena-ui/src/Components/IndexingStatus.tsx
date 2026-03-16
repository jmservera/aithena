import { useStatus } from '../hooks/status';

function ServiceDot({ serviceStatus }: { serviceStatus: string }) {
  const isUp = serviceStatus === 'up';
  return (
    <span
      className={`health-dot ${isUp ? 'health-dot--ok' : 'health-dot--error'}`}
      title={serviceStatus}
      aria-label={serviceStatus}
    />
  );
}

function IndexingStatus() {
  const { data, loading, error, lastUpdated } = useStatus();

  if (loading && !data) {
    return (
      <main className="status-main">
        <p className="status-loading">Loading status…</p>
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className="status-main">
        <p className="status-error">⚠ {error}</p>
      </main>
    );
  }

  const indexing = data?.indexing;
  const services = data?.services;
  const solr = data?.solr;

  return (
    <main className="status-main">
      <header className="status-header">
        <h2 className="status-title">🟢 System Status</h2>
        {lastUpdated && (
          <span className="status-updated">Updated {lastUpdated.toLocaleTimeString()}</span>
        )}
        {error && <span className="status-error-inline">⚠ {error}</span>}
      </header>

      <section className="status-section">
        <h3 className="status-section-title">Indexing Progress</h3>
        <div className="indexing-grid">
          <div className="indexing-card">
            <span className="indexing-value">{indexing?.total_discovered ?? '—'}</span>
            <span className="indexing-label">Discovered</span>
          </div>
          <div className="indexing-card indexing-card--ok">
            <span className="indexing-value">{indexing?.indexed ?? '—'}</span>
            <span className="indexing-label">Indexed</span>
          </div>
          <div className="indexing-card indexing-card--error">
            <span className="indexing-value">{indexing?.failed ?? '—'}</span>
            <span className="indexing-label">Failed</span>
          </div>
          <div className="indexing-card indexing-card--pending">
            <span className="indexing-value">{indexing?.pending ?? '—'}</span>
            <span className="indexing-label">Pending</span>
          </div>
        </div>
      </section>

      <section className="status-section">
        <h3 className="status-section-title">Service Health</h3>
        <ul className="service-list">
          <li className="service-item">
            <ServiceDot serviceStatus={services?.solr ?? 'unknown'} />
            <span className="service-name">Solr</span>
            <span className="service-detail">
              {solr
                ? `${solr.status} · ${solr.nodes} node${solr.nodes !== 1 ? 's' : ''} · ${solr.docs_indexed} docs`
                : (services?.solr ?? '—')}
            </span>
          </li>
          <li className="service-item">
            <ServiceDot serviceStatus={services?.redis ?? 'unknown'} />
            <span className="service-name">Redis</span>
            <span className="service-detail">{services?.redis ?? '—'}</span>
          </li>
          <li className="service-item">
            <ServiceDot serviceStatus={services?.rabbitmq ?? 'unknown'} />
            <span className="service-name">RabbitMQ</span>
            <span className="service-detail">{services?.rabbitmq ?? '—'}</span>
          </li>
        </ul>
      </section>
    </main>
  );
}

export default IndexingStatus;
