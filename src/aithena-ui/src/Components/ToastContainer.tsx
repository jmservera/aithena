import { useIntl } from 'react-intl';
import { useToast } from '../contexts/ToastContext';

function ToastContainer() {
  const intl = useIntl();
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-live="polite" aria-relevant="additions">
      {toasts.map((toast, index) => (
        <div key={toast.id} className={`toast toast--${toast.type}`} role="status">
          <span className="toast-message">{toast.message}</span>
          <button
            type="button"
            className="toast-dismiss"
            onClick={() => removeToast(toast.id)}
            aria-label={intl.formatMessage(
              { id: 'toast.dismiss' },
              { position: index + 1, total: toasts.length }
            )}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export default ToastContainer;
