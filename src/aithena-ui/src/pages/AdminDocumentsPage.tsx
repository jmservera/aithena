import { useIntl } from 'react-intl';

function AdminDocumentsPage() {
  const intl = useIntl();

  return (
    <div className="admin-placeholder">
      <h2>{intl.formatMessage({ id: 'adminPages.documents.title' })}</h2>
      <p>{intl.formatMessage({ id: 'adminPages.documents.placeholder' })}</p>
    </div>
  );
}

export default AdminDocumentsPage;
