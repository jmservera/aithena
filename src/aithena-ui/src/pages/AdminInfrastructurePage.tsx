import { useIntl } from 'react-intl';

function AdminInfrastructurePage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.infrastructure.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.infrastructure.placeholder' })}</p>
    </div>
  );
}

export default AdminInfrastructurePage;
