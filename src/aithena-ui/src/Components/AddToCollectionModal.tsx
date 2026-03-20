import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { Plus, Search } from 'lucide-react';
import {
  type Collection,
  type CollectionCreateRequest,
  addItemsToCollection,
  createCollection,
  fetchCollections,
} from '../services/collectionsApi';

interface AddToCollectionModalProps {
  open: boolean;
  onClose: () => void;
  documentIds: string[];
  onSuccess: (collectionName: string, count: number) => void;
}

function AddToCollectionModal({
  open,
  onClose,
  documentIds,
  onSuccess,
}: AddToCollectionModalProps) {
  const intl = useIntl();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const overlayRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void fetchCollections()
      .then((data) => {
        if (!cancelled) setCollections(data);
      })
      .catch(() => {
        if (!cancelled) setError(intl.formatMessage({ id: 'collections.loadError' }));
      });
    return () => {
      cancelled = true;
    };
  }, [open, intl]);

  useEffect(() => {
    if (open) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setQuery('');
      setShowCreate(false);
      setNewName('');
      setError(null);
      setBusy(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      requestAnimationFrame(() => searchInputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const filtered = collections.filter((c) => c.name.toLowerCase().includes(query.toLowerCase()));

  const handleAddTo = useCallback(
    async (collectionId: string, collectionName: string) => {
      setBusy(true);
      setError(null);
      try {
        await addItemsToCollection(collectionId, documentIds);
        onSuccess(collectionName, documentIds.length);
        onClose();
      } catch {
        setError(intl.formatMessage({ id: 'collections.addError' }));
      } finally {
        setBusy(false);
      }
    },
    [documentIds, onSuccess, onClose, intl]
  );

  const handleCreateAndAdd = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = newName.trim();
      if (!trimmed) return;
      setBusy(true);
      setError(null);
      try {
        const req: CollectionCreateRequest = { name: trimmed };
        const created = await createCollection(req);
        await addItemsToCollection(created.id, documentIds);
        onSuccess(created.name, documentIds.length);
        onClose();
      } catch {
        setError(intl.formatMessage({ id: 'collections.addError' }));
      } finally {
        setBusy(false);
      }
    },
    [newName, documentIds, onSuccess, onClose, intl]
  );

  if (!open) return null;

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      className="collection-modal-overlay"
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={intl.formatMessage({ id: 'collections.addToCollectionTitle' })}
      tabIndex={-1}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div className="collection-modal add-to-collection-modal">
        <h3 className="collection-modal-title">
          {intl.formatMessage({ id: 'collections.addToCollectionTitle' })}
        </h3>

        {documentIds.length > 1 && (
          <p className="add-to-collection-count">
            {intl.formatMessage({ id: 'collections.addingCount' }, { count: documentIds.length })}
          </p>
        )}

        {error && (
          <p className="add-to-collection-error" role="alert">
            {error}
          </p>
        )}

        <div className="add-to-collection-search">
          <Search size={14} aria-hidden="true" />
          <input
            ref={searchInputRef}
            type="text"
            className="collection-modal-input"
            placeholder={intl.formatMessage({ id: 'collections.searchCollections' })}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={intl.formatMessage({ id: 'collections.searchCollections' })}
          />
        </div>

        <ul className="add-to-collection-list" role="listbox">
          {filtered.map((col) => (
            <li key={col.id} role="option" aria-selected={false}>
              <button
                type="button"
                className="add-to-collection-option"
                disabled={busy}
                onClick={() => handleAddTo(col.id, col.name)}
              >
                <span className="add-to-collection-option-name">{col.name}</span>
                <span className="add-to-collection-option-count">
                  {intl.formatMessage({ id: 'collections.itemCount' }, { count: col.item_count })}
                </span>
              </button>
            </li>
          ))}
          {filtered.length === 0 && !showCreate && (
            <li className="add-to-collection-empty">
              {intl.formatMessage({ id: 'collections.noCollectionsFound' })}
            </li>
          )}
        </ul>

        {!showCreate ? (
          <button
            type="button"
            className="add-to-collection-create-btn"
            onClick={() => setShowCreate(true)}
            disabled={busy}
          >
            <Plus size={16} aria-hidden="true" />
            {intl.formatMessage({ id: 'collections.createNewInline' })}
          </button>
        ) : (
          <form className="add-to-collection-create-form" onSubmit={handleCreateAndAdd}>
            <input
              type="text"
              className="collection-modal-input"
              placeholder={intl.formatMessage({ id: 'collections.namePlaceholder' })}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              maxLength={200}
              required
              aria-label={intl.formatMessage({ id: 'collections.nameLabel' })}
            />
            <div className="add-to-collection-create-actions">
              <button
                type="button"
                className="collection-modal-cancel-btn"
                onClick={() => setShowCreate(false)}
                disabled={busy}
              >
                {intl.formatMessage({ id: 'collections.cancel' })}
              </button>
              <button
                type="submit"
                className="collection-modal-submit-btn"
                disabled={!newName.trim() || busy}
              >
                {intl.formatMessage({ id: 'collections.createAndAdd' })}
              </button>
            </div>
          </form>
        )}

        <div className="collection-modal-actions">
          <button type="button" className="collection-modal-cancel-btn" onClick={onClose}>
            {intl.formatMessage({ id: 'collections.cancel' })}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AddToCollectionModal;
