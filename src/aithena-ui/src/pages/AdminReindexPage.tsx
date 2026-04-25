import { useState } from 'react';
import { useIntl } from 'react-intl';
import { useAdminReindex } from '../hooks/reindex';
import ConfirmDialog from '../Components/ConfirmDialog';

const DEFAULT_COLLECTION = 'books';

function AdminReindexPage() {
  const intl = useIntl();
  const { loading, error, result, triggerReindex, reset } = useAdminReindex();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [collection] = useState(DEFAULT_COLLECTION);

  function handleReindexClick() {
    reset();
    setConfirmOpen(true);
  }

  async function handleConfirm() {
    setConfirmOpen(false);
    await triggerReindex(collection);
  }

  function handleCancel() {
    setConfirmOpen(false);
  }

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h2 className="admin-title">{intl.formatMessage({ id: 'adminPages.reindex.title' })}</h2>
      </div>

      <section
        className="admin-reindex-description"
        aria-label={intl.formatMessage({ id: 'adminReindex.descriptionAria' })}
      >
        <p>{intl.formatMessage({ id: 'adminReindex.intro' })}</p>
        <ol className="admin-reindex-steps">
          <li>{intl.formatMessage({ id: 'adminReindex.step1' }, { collection })}</li>
          <li>{intl.formatMessage({ id: 'adminReindex.step2' })}</li>
          <li>{intl.formatMessage({ id: 'adminReindex.step3' })}</li>
          <li>{intl.formatMessage({ id: 'adminReindex.step4' })}</li>
        </ol>
        <p className="admin-reindex-warning">
          ⚠️ {intl.formatMessage({ id: 'adminReindex.searchUnavailable' })}
        </p>
      </section>

      <div className="admin-reindex-action">
        <button
          type="button"
          className="admin-btn admin-btn--primary"
          disabled={loading}
          onClick={handleReindexClick}
        >
          {loading
            ? intl.formatMessage({ id: 'adminReindex.inProgress' })
            : intl.formatMessage({ id: 'adminReindex.startButton' })}
        </button>

        {loading && (
          <p className="admin-reindex-spinner" role="status" aria-live="polite">
            {intl.formatMessage({ id: 'adminReindex.spinnerText' })}
          </p>
        )}
      </div>

      {result && (
        <div
          className="admin-reindex-result admin-reindex-result--success"
          role="status"
          aria-live="polite"
        >
          <p>
            <strong>{intl.formatMessage({ id: 'adminReindex.successTitle' })}</strong>
          </p>
          <ul>
            <li>
              {intl.formatMessage(
                { id: 'adminReindex.successCollection' },
                { collection: result.collection, status: result.solr }
              )}
            </li>
            <li>
              {intl.formatMessage(
                { id: 'adminReindex.successRedis' },
                { count: String(result.redis_cleared) }
              )}
            </li>
          </ul>
          {result.message && <p>{result.message}</p>}
        </div>
      )}

      {error && (
        <div
          className="admin-reindex-result admin-reindex-result--error"
          role="alert"
          aria-live="assertive"
        >
          <p>
            {intl.formatMessage({ id: 'adminReindex.errorPrefix' })}: {error}
          </p>
        </div>
      )}

      <ConfirmDialog
        open={confirmOpen}
        titleId="adminReindex.confirmTitle"
        messageId="adminReindex.confirmMessage"
        messageValues={{ collection }}
        confirmLabelId="adminReindex.confirmButton"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </div>
  );
}

export default AdminReindexPage;
