import { useIntl } from 'react-intl';

function AdminReindexPage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.reindex.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.reindex.placeholder' })}</p>
    </div>
  );
}

export default AdminReindexPage;
