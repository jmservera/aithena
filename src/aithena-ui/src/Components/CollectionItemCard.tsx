import { useCallback, useState } from 'react';
import { useIntl } from 'react-intl';
import { Trash2 } from 'lucide-react';
import { type CollectionItem } from '../services/collectionsApi';
import NoteEditor from './NoteEditor';

interface CollectionItemCardProps {
  item: CollectionItem;
  onRemove: (itemId: string) => void;
  onSaveNote: (itemId: string, note: string) => void;
  saving?: boolean;
}

function CollectionItemCard({ item, onRemove, onSaveNote, saving }: CollectionItemCardProps) {
  const intl = useIntl();
  const [confirmRemove, setConfirmRemove] = useState(false);

  const handleRemoveClick = useCallback(() => {
    if (confirmRemove) {
      onRemove(item.id);
      setConfirmRemove(false);
    } else {
      setConfirmRemove(true);
    }
  }, [confirmRemove, item.id, onRemove]);

  const handleCancelRemove = useCallback(() => setConfirmRemove(false), []);

  return (
    <article className="collection-item-card" data-testid={`collection-item-${item.id}`}>
      <div className="collection-item-header">
        <div className="collection-item-info">
          <h4 className="collection-item-title">{item.title}</h4>
          <div className="collection-item-meta">
            {item.author && <span className="collection-item-author">{item.author}</span>}
            {item.year && <span className="collection-item-year">{item.year}</span>}
          </div>
        </div>
        <div className="collection-item-actions">
          {confirmRemove && (
            <button
              type="button"
              className="collection-item-cancel-btn"
              onClick={handleCancelRemove}
            >
              {intl.formatMessage({ id: 'collections.cancelRemove' })}
            </button>
          )}
          <button
            type="button"
            className={`collection-item-remove-btn${confirmRemove ? ' collection-item-remove-btn--confirm' : ''}`}
            onClick={handleRemoveClick}
            aria-label={intl.formatMessage({ id: 'collections.removeItem' }, { title: item.title })}
            title={intl.formatMessage({ id: 'collections.removeItem' }, { title: item.title })}
          >
            <Trash2 size={16} aria-hidden="true" />
            {confirmRemove
              ? intl.formatMessage({ id: 'collections.confirmRemove' })
              : intl.formatMessage({ id: 'collections.remove' })}
          </button>
        </div>
      </div>
      <NoteEditor itemId={item.id} initialNote={item.note} onSave={onSaveNote} saving={saving} />
    </article>
  );
}

export default CollectionItemCard;
