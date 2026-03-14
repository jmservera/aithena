import { useStatus, ServiceHealth, FailedDocument } from "../hooks/status";

function HealthDot({ health }: { health: ServiceHealth }) {
  const isOk = health.status === "ok";
  const isUnknown = health.status === "unknown";
  const label = isOk ? "healthy" : isUnknown ? "unknown" : "error";
  return (
    <span
      className={`health-dot health-dot--${label}`}
      title={health.message ?? label}
      aria-label={label}
    />
  );
}

function ServiceRow({ name, health }: { name: string; health: ServiceHealth }) {
  return (
    <div className="service-row">
      <HealthDot health={health} />
      <span className="service-name">{name}</span>
      {health.message && (
        <span className="service-message">{health.message}</span>
      )}
    </div>
  );
}

function ProgressBar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="progress-bar-track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function FailedDocRow({ doc }: { doc: FailedDocument }) {
  return (
    <li className="failed-doc-item">
      <span className="failed-doc-path" title={doc.path}>{doc.path}</span>
      {doc.stage && <span className="failed-doc-stage">[{doc.stage}]</span>}
      <span className="failed-doc-error">{doc.error}</span>
    </li>
  );
}

function IndexingStatus() {
  const { data, loading, error } = useStatus();

  if (loading && !data) {
    return <div className="status-loading">Loading status…</div>;
  }

  if (error) {
    return (
      <div className="search-error status-error" role="alert">
        ⚠️ {error}
      </div>
    );
  }

  if (!data) {
    return <div className="search-empty">No status data available.</div>;
  }

  const { indexing, services, failed_documents } = data;
  const total = indexing.discovered;

  return (
    <div className="indexing-status">
      <section className="status-section">
        <h2 className="status-section-title">Indexing Progress</h2>
        <ProgressBar value={indexing.indexed} total={total} />
        <div className="indexing-stats">
          <div className="stat-item">
            <span className="stat-label">Discovered</span>
            <span className="stat-value">{indexing.discovered}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Indexed</span>
            <span className="stat-value stat-value--ok">{indexing.indexed}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Pending</span>
            <span className="stat-value stat-value--pending">{indexing.pending}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Failed</span>
            <span className={`stat-value${indexing.failed > 0 ? " stat-value--error" : ""}`}>
              {indexing.failed}
            </span>
          </div>
        </div>
      </section>

      <section className="status-section">
        <h2 className="status-section-title">Service Health</h2>
        <div className="services-list">
          <ServiceRow name="Solr" health={services.solr} />
          <ServiceRow name="Redis" health={services.redis} />
          <ServiceRow name="RabbitMQ" health={services.rabbitmq} />
        </div>
      </section>

      {failed_documents.length > 0 && (
        <section className="status-section">
          <h2 className="status-section-title">
            Failed Documents ({failed_documents.length})
          </h2>
          <ul className="failed-docs-list">
            {failed_documents.map((doc) => (
              <FailedDocRow key={doc.path} doc={doc} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default IndexingStatus;
