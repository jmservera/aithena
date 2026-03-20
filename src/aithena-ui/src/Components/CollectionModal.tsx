import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

interface CollectionModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, description: string) => void;
  /** Pre-fill for edit mode. */
  initialName?: string;
  initialDescription?: string;
  titleId: string;
  submitLabelId: string;
}

function CollectionModal({
  open,
  onClose,
  onSubmit,
  initialName = '',
  initialDescription = '',
  titleId,
  submitLabelId,
}: CollectionModalProps) {
  const intl = useIntl();
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const overlayRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Focus the name input when the modal opens
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => nameInputRef.current?.focus());
    }
  }, [open]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = name.trim();
      if (!trimmed) return;
      onSubmit(trimmed, description.trim());
    },
    [name, description, onSubmit]
  );

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      className="collection-modal-overlay"
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={intl.formatMessage({ id: titleId })}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div className="collection-modal">
        <h3 className="collection-modal-title">{intl.formatMessage({ id: titleId })}</h3>
        <form className="collection-modal-form" onSubmit={handleSubmit}>
          <label className="collection-modal-label" htmlFor="collection-name">
            {intl.formatMessage({ id: 'collections.nameLabel' })}
          </label>
          <input
            ref={nameInputRef}
            id="collection-name"
            className="collection-modal-input"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
            placeholder={intl.formatMessage({ id: 'collections.namePlaceholder' })}
          />
          <label className="collection-modal-label" htmlFor="collection-description">
            {intl.formatMessage({ id: 'collections.descriptionLabel' })}
          </label>
          <textarea
            id="collection-description"
            className="collection-modal-textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={1000}
            rows={3}
            placeholder={intl.formatMessage({ id: 'collections.descriptionPlaceholder' })}
          />
          <div className="collection-modal-actions">
            <button type="button" className="collection-modal-cancel-btn" onClick={onClose}>
              {intl.formatMessage({ id: 'collections.cancel' })}
            </button>
            <button type="submit" className="collection-modal-submit-btn" disabled={!name.trim()}>
              {intl.formatMessage({ id: submitLabelId })}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CollectionModal;
