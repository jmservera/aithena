import { useCallback, useState } from 'react';
import { useIntl } from 'react-intl';
import { FileText, Trash2 } from 'lucide-react';
import { type CollectionItem } from '../services/collectionsApi';
import NoteEditor from './NoteEditor';

interface CollectionItemCardProps {
  item: CollectionItem;
  onRemove: (itemId: string) => void;
  onSaveNote: (itemId: string, note: string) => void;
  onOpenPdf?: (item: CollectionItem) => void;
  saving?: boolean;
}

function CollectionItemThumbnail({ src, alt }: { src: string; alt: string }) {
  const [error, setError] = useState(false);

  if (error) {
    return (
      <div className="book-card-thumbnail book-card-thumbnail--placeholder" aria-hidden="true">
        <FileText size={32} />
      </div>
    );
  }

  return (
    <img
      className="book-card-thumbnail"
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setError(true)}
    />
  );
}

function CollectionItemCard({
  item,
  onRemove,
  onSaveNote,
  onOpenPdf,
  saving,
}: CollectionItemCardProps) {
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

  const handleOpenPdf = useCallback(() => {
    onOpenPdf?.(item);
  }, [item, onOpenPdf]);

  return (
    <article className="collection-item-card" data-testid={`collection-item-${item.id}`}>
      <div className="book-card-body">
        {item.thumbnail_url ? (
          <CollectionItemThumbnail src={item.thumbnail_url} alt={item.title} />
        ) : (
          <div className="book-card-thumbnail book-card-thumbnail--placeholder" aria-hidden="true">
            <FileText size={32} />
          </div>
        )}
        <div className="book-card-content">
          <div className="collection-item-header">
            <div className="collection-item-info">
              <h3 className="book-title">{item.title}</h3>
              <div className="book-meta">
                {item.author && (
                  <span className="book-meta-item">
                    <span className="book-meta-label">
                      {intl.formatMessage({ id: 'book.metaAuthor' })}
                    </span>{' '}
                    {item.author}
                  </span>
                )}
                {item.year && (
                  <span className="book-meta-item">
                    <span className="book-meta-label">
                      {intl.formatMessage({ id: 'book.metaYear' })}
                    </span>{' '}
                    {item.year}
                  </span>
                )}
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
                aria-label={intl.formatMessage(
                  { id: 'collections.removeItem' },
                  { title: item.title }
                )}
                title={intl.formatMessage({ id: 'collections.removeItem' }, { title: item.title })}
              >
                <Trash2 size={16} aria-hidden="true" />
                {confirmRemove
                  ? intl.formatMessage({ id: 'collections.confirmRemove' })
                  : intl.formatMessage({ id: 'collections.remove' })}
              </button>
            </div>
          </div>
          <div className="book-card-footer">
            {item.document_url && onOpenPdf && (
              <button
                type="button"
                className="open-pdf-btn"
                onClick={handleOpenPdf}
                aria-label={intl.formatMessage({ id: 'book.openPdfFor' }, { title: item.title })}
              >
                <FileText size={20} aria-hidden="true" />{' '}
                {intl.formatMessage({ id: 'book.openPdf' })}
              </button>
            )}
          </div>
        </div>
      </div>
      <NoteEditor itemId={item.id} initialNote={item.note} onSave={onSaveNote} saving={saving} />
    </article>
  );
}

export default CollectionItemCard;
