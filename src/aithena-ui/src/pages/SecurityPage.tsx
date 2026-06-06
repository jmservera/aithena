import { ExternalLink, RefreshCw, ShieldCheck, Users } from 'lucide-react';
import { useIntl } from 'react-intl';
import { Link } from 'react-router-dom';
import {
  buildSolrSecurityUrl,
  getServiceAdminUrl,
  useAdminInfrastructure,
} from '../hooks/useAdminInfrastructure';

function SecurityPage() {
  const intl = useIntl();
  const { data, loading, error, refresh } = useAdminInfrastructure();
  const fmt = (id: string) => intl.formatMessage({ id });
  const solrService = data?.services.find((service) => service.name === 'solr');
  const solrAdminUrl = data?.solr_admin_url ?? getServiceAdminUrl(data, 'solr', '/admin/solr/');
  const solrSecurityUrl = buildSolrSecurityUrl(solrAdminUrl);
  const solrIsDown = solrService?.status === 'down';

  return (
    <main className="admin-page security-page">
      <header className="admin-header">
        <h2 className="admin-title">{fmt('security.title')}</h2>
        <div className="admin-actions">
          <button
            type="button"
            className="admin-btn"
            onClick={refresh}
            disabled={loading}
            aria-label={fmt('security.refreshLabel')}
          >
            <RefreshCw size={14} aria-hidden="true" className={loading ? 'spin' : ''} />
            {fmt('infra.refresh')}
          </button>
          <a
            className="admin-btn admin-btn--primary security-open-link"
            href={solrSecurityUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            {fmt('security.openSolr')}
            <ExternalLink size={14} aria-hidden="true" />
          </a>
        </div>
      </header>

      {error && (
        <div className="admin-error-banner" role="alert">
          {fmt('admin.errorPrefix')} {error}
        </div>
      )}

      {solrIsDown && (
        <div className="admin-error-banner" role="alert">
          {fmt('security.solrDown')}
        </div>
      )}

      <section className="security-hero" aria-labelledby="security-overview-title">
        <ShieldCheck size={32} aria-hidden="true" />
        <div>
          <h3 id="security-overview-title">{fmt('security.overviewTitle')}</h3>
          <p>{fmt('security.overviewBody')}</p>
        </div>
      </section>

      <section className="security-card-grid" aria-label={fmt('security.sectionsAria')}>
        <article className="security-card">
          <h3>{fmt('security.solrCardTitle')}</h3>
          <p>{fmt('security.solrCardBody')}</p>
          <ol className="security-steps">
            <li>{fmt('security.stepOpen')}</li>
            <li>{fmt('security.stepAuthenticate')}</li>
            <li>{fmt('security.stepUsers')}</li>
            <li>{fmt('security.stepRoles')}</li>
          </ol>
          <p className="security-note">{fmt('security.solrNote')}</p>
        </article>

        <article className="security-card">
          <h3>{fmt('security.appCardTitle')}</h3>
          <p>{fmt('security.appCardBody')}</p>
          <Link className="admin-btn" to="/admin/users">
            <Users size={14} aria-hidden="true" />
            {fmt('security.manageAppUsers')}
          </Link>
        </article>

        <article className="security-card">
          <h3>{fmt('security.guardrailsTitle')}</h3>
          <ul className="security-guardrails">
            <li>{fmt('security.guardrailAuth')}</li>
            <li>{fmt('security.guardrailNoMutations')}</li>
            <li>{fmt('security.guardrailNoSecrets')}</li>
            <li>{fmt('security.guardrailReview')}</li>
          </ul>
        </article>
      </section>
    </main>
  );
}

export default SecurityPage;
