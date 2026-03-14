import { useStatus } from '../hooks/status';
import type { ServiceHealth, FailedDocument } from '../hooks/status';

function HealthDot({ health }: { health: ServiceHealth }) {
  const isOk = health.status === 'ok' && health.reachable;
  return (
    <span
      className={`health-dot ${isOk ? 'health-dot--ok' : 'health-dot--error'}`}
      title={health.detail ?? health.status}
      aria-label={isOk ? 'ok' : 'error'}
    />
  );
}

function FailedDocRow({ doc }: { doc: FailedDocument }) {
  return (
    <li className="failed-doc-item">
      <span className="failed-doc-id">{doc.file_path ?? doc.id}</span>
      {doc.error && <span className="failed-doc-error">{doc.error}</span>}
    </li>
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
  const failedDocs = data?.failed_documents ?? [];

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
            <span className="indexing-value">{indexing?.discovered ?? '—'}</span>
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
          {services && (
            <>
              <li className="service-item">
                <HealthDot health={services.solr} />
                <span className="service-name">Solr</span>
                <span className="service-detail">
                  {services.solr.detail ?? services.solr.status}
                </span>
              </li>
              <li className="service-item">
                <HealthDot health={services.redis} />
                <span className="service-name">Redis</span>
                <span className="service-detail">
                  {services.redis.detail ?? services.redis.status}
                </span>
              </li>
              <li className="service-item">
                <HealthDot health={services.rabbitmq} />
                <span className="service-name">RabbitMQ</span>
                <span className="service-detail">
                  {services.rabbitmq.detail ?? services.rabbitmq.status}
                </span>
              </li>
            </>
          )}
        </ul>
      </section>

      {failedDocs.length > 0 && (
        <section className="status-section">
          <h3 className="status-section-title">Failed Documents ({failedDocs.length})</h3>
          <ul className="failed-doc-list">
            {failedDocs.map((doc, i) => (
              <FailedDocRow key={`${doc.id}-${i}`} doc={doc} />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

export default IndexingStatus;
