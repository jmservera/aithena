import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

interface ConfirmDialogProps {
  open: boolean;
  titleId: string;
  messageId: string;
  messageValues?: Record<string, string>;
  confirmLabelId: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({
  open,
  titleId,
  messageId,
  messageValues,
  confirmLabelId,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const intl = useIntl();
  const [busy, setBusy] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleConfirm = useCallback(async () => {
    setBusy(true);
    try {
      await Promise.resolve(onConfirm());
    } finally {
      setBusy(false);
    }
  }, [onConfirm]);

  // Focus the overlay when dialog opens so Escape key works
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => overlayRef.current?.focus());
    }
  }, [open]);

  if (!open) return null;

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      className="collection-modal-overlay"
      ref={overlayRef}
      role="alertdialog"
      aria-modal="true"
      aria-label={intl.formatMessage({ id: titleId })}
      tabIndex={-1}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onCancel();
      }}
    >
      <div className="collection-modal">
        <h3 className="collection-modal-title">{intl.formatMessage({ id: titleId })}</h3>
        <p className="collection-modal-body">
          {intl.formatMessage({ id: messageId }, messageValues)}
        </p>
        <div className="collection-modal-actions">
          <button type="button" className="collection-modal-cancel-btn" onClick={onCancel}>
            {intl.formatMessage({ id: 'collections.cancel' })}
          </button>
          <button
            type="button"
            className="collection-modal-submit-btn collection-modal-submit-btn--danger"
            onClick={handleConfirm}
            disabled={busy}
          >
            {intl.formatMessage({ id: confirmLabelId })}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
