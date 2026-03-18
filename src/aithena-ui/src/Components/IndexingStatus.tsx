import { useIntl } from 'react-intl';
import { CheckCircle } from 'lucide-react';

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
  const intl = useIntl();
  const { data, loading, error, lastUpdated } = useStatus();

  if (loading && !data) {
    return (
      <main className="status-main">
        <p className="status-loading">{intl.formatMessage({ id: 'indexing.loading' })}</p>
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className="status-main">
        <p className="status-error">
          {intl.formatMessage({ id: 'error.prefix' })} {error}
        </p>
      </main>
    );
  }

  const indexing = data?.indexing;
  const services = data?.services;
  const solr = data?.solr;

  return (
    <main className="status-main">
      <header className="status-header">
        <h2 className="status-title">
          <CheckCircle size={20} aria-hidden="true" />{' '}
          {intl.formatMessage({ id: 'indexing.title' })}
        </h2>
        {lastUpdated && (
          <span className="status-updated">
            {intl.formatMessage(
              { id: 'indexing.updated' },
              { time: lastUpdated.toLocaleTimeString() }
            )}
          </span>
        )}
        {error && (
          <span className="status-error-inline">
            {intl.formatMessage({ id: 'error.prefix' })} {error}
          </span>
        )}
      </header>

      <section className="status-section">
        <h3 className="status-section-title">{intl.formatMessage({ id: 'indexing.progress' })}</h3>
        <div className="indexing-grid">
          <div className="indexing-card">
            <span className="indexing-value">{indexing?.total_discovered ?? '—'}</span>
            <span className="indexing-label">
              {intl.formatMessage({ id: 'indexing.discovered' })}
            </span>
          </div>
          <div className="indexing-card indexing-card--ok">
            <span className="indexing-value">{indexing?.indexed ?? '—'}</span>
            <span className="indexing-label">{intl.formatMessage({ id: 'indexing.indexed' })}</span>
          </div>
          <div className="indexing-card indexing-card--error">
            <span className="indexing-value">{indexing?.failed ?? '—'}</span>
            <span className="indexing-label">{intl.formatMessage({ id: 'indexing.failed' })}</span>
          </div>
          <div className="indexing-card indexing-card--pending">
            <span className="indexing-value">{indexing?.pending ?? '—'}</span>
            <span className="indexing-label">{intl.formatMessage({ id: 'indexing.pending' })}</span>
          </div>
        </div>
      </section>

      <section className="status-section">
        <h3 className="status-section-title">
          {intl.formatMessage({ id: 'indexing.serviceHealth' })}
        </h3>
        <ul className="service-list">
          <li className="service-item">
            <ServiceDot serviceStatus={services?.solr ?? 'unknown'} />
            <span className="service-name">{intl.formatMessage({ id: 'indexing.solr' })}</span>
            <span className="service-detail">
              {solr
                ? intl.formatMessage(
                    { id: 'indexing.solrDetail' },
                    { status: solr.status, nodes: solr.nodes, docs: solr.docs_indexed }
                  )
                : (services?.solr ?? '—')}
            </span>
          </li>
          <li className="service-item">
            <ServiceDot serviceStatus={services?.redis ?? 'unknown'} />
            <span className="service-name">{intl.formatMessage({ id: 'indexing.redis' })}</span>
            <span className="service-detail">{services?.redis ?? '—'}</span>
          </li>
          <li className="service-item">
            <ServiceDot serviceStatus={services?.rabbitmq ?? 'unknown'} />
            <span className="service-name">{intl.formatMessage({ id: 'indexing.rabbitmq' })}</span>
            <span className="service-detail">{services?.rabbitmq ?? '—'}</span>
          </li>
        </ul>
      </section>
    </main>
  );
}

export default IndexingStatus;
