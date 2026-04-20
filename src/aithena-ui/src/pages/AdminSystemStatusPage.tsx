import { useIntl } from 'react-intl';

function AdminSystemStatusPage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.systemStatus.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.systemStatus.placeholder' })}</p>
    </div>
  );
}

export default AdminSystemStatusPage;
