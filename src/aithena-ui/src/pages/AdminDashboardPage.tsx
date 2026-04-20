import { useIntl } from 'react-intl';

function AdminDashboardPage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.dashboard.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.dashboard.placeholder' })}</p>
    </div>
  );
}

export default AdminDashboardPage;
