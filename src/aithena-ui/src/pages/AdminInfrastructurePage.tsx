import { useIntl } from 'react-intl';
import { Database, ExternalLink, MessageSquare, Server, RefreshCw } from 'lucide-react';
import { useAdminInfrastructure, type ServiceEndpoint } from '../hooks/useAdminInfrastructure';

/* ── Sub-components ───────────────────────────────────────────────────── */

interface ServiceCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  url: string;
}

function ServiceCard({ icon, title, description, url }: ServiceCardProps) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="infra-card infra-card--link">
      <div className="infra-card-icon" aria-hidden="true">
        {icon}
      </div>
      <div className="infra-card-body">
        <h3 className="infra-card-title">
          {title}
          <ExternalLink size={14} aria-hidden="true" />
        </h3>
        <p className="infra-card-description">{description}</p>
      </div>
    </a>
  );
}

function ConnectionRow({ service }: { service: ServiceEndpoint }) {
  return (
    <tr>
      <td className="infra-service-name">{service.name}</td>
      <td>{service.type}</td>
      <td>{service.url}</td>
      <td>
        <span
          className={`infra-badge ${service.status === 'connected' ? 'infra-badge--ok' : 'infra-badge--error'}`}
        >
          {service.status}
        </span>
      </td>
    </tr>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

function AdminInfrastructurePage() {
  const intl = useIntl();
  const { data, loading, error, refresh } = useAdminInfrastructure();

  const fmt = (id: string, values?: Record<string, string | number>) =>
    intl.formatMessage({ id }, values);

  const solrUrl = data?.solr_admin_url ?? '/admin/solr/';
  const rabbitmqUrl = data?.rabbitmq_admin_url ?? '/admin/rabbitmq/';
  const redisUrl = data?.redis_admin_url ?? '/admin/redis/';

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">{fmt('adminPages.infrastructure.title')}</h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading}
            aria-label={fmt('infra.refreshLabel')}
          >
            <RefreshCw size={14} aria-hidden="true" className={loading ? 'spin' : ''} />
            {fmt('infra.refresh')}
          </button>
        </div>
      </header>

      {error && (
        <div className="admin-error-banner" role="alert">
          {fmt('admin.errorPrefix')} {error}
        </div>
      )}

      {loading && !data && <p className="admin-loading">{fmt('infra.loading')}</p>}

      {/* ── Service link cards ──────────────────────────────── */}
      <section aria-label={fmt('admin.infra.sectionAria')}>
        <div className="infra-cards-grid">
          <ServiceCard
            icon={<Database size={24} />}
            title={fmt('admin.infra.solr')}
            description={fmt('admin.infra.solrDescription')}
            url={solrUrl}
          />
          <ServiceCard
            icon={<MessageSquare size={24} />}
            title={fmt('admin.infra.rabbitmq')}
            description={fmt('admin.infra.rabbitmqDescription')}
            url={rabbitmqUrl}
          />
          <ServiceCard
            icon={<Server size={24} />}
            title={fmt('infra.redis')}
            description={fmt('infra.redisDescription')}
            url={redisUrl}
          />
        </div>
      </section>

      {/* ── Connection details table ──────────────────────── */}
      {data?.services && data.services.length > 0 && (
        <section className="infra-connections" aria-label={fmt('infra.connectionsAria')}>
          <h3 className="infra-section-title">{fmt('infra.connectionsTitle')}</h3>
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th scope="col">{fmt('infra.colService')}</th>
                  <th scope="col">{fmt('infra.colType')}</th>
                  <th scope="col">{fmt('infra.colEndpoint')}</th>
                  <th scope="col">{fmt('infra.colStatus')}</th>
                </tr>
              </thead>
              <tbody>
                {data.services.map((s) => (
                  <ConnectionRow key={s.name} service={s} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

export default AdminInfrastructurePage;
