import { useIntl } from 'react-intl';

function AdminLogsPage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.logs.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.logs.placeholder' })}</p>
    </div>
  );
}

export default AdminLogsPage;
