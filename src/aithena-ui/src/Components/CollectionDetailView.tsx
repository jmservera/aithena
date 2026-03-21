import { useCallback, useMemo, useState } from 'react';
import { useIntl } from 'react-intl';
import { ArrowUpDown, Pencil, Trash2 } from 'lucide-react';
import { type CollectionDetail, type CollectionItem } from '../services/collectionsApi';
import CollectionItemCard from './CollectionItemCard';

type SortKey = 'title' | 'author' | 'year' | 'added_at';
type SortDir = 'asc' | 'desc';

interface CollectionDetailViewProps {
  detail: CollectionDetail;
  onRemoveItem: (itemId: string) => void;
  onSaveNote: (itemId: string, note: string) => void;
  onEdit: () => void;
  onDelete: () => void;
  saving?: boolean;
}

function sortItems(items: CollectionItem[], key: SortKey, dir: SortDir): CollectionItem[] {
  const sorted = [...items].sort((a, b) => {
    let cmp = 0;
    switch (key) {
      case 'title':
        cmp = (a.title ?? '').localeCompare(b.title ?? '');
        break;
      case 'author':
        cmp = (a.author ?? '').localeCompare(b.author ?? '');
        break;
      case 'year':
        cmp = (a.year ?? 0) - (b.year ?? 0);
        break;
      case 'added_at':
        cmp = a.added_at.localeCompare(b.added_at);
        break;
    }
    return dir === 'asc' ? cmp : -cmp;
  });
  return sorted;
}

function CollectionDetailView({
  detail,
  onRemoveItem,
  onSaveNote,
  onEdit,
  onDelete,
  saving,
}: CollectionDetailViewProps) {
  const intl = useIntl();
  const [sortKey, setSortKey] = useState<SortKey>('added_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const sortedItems = useMemo(
    () => sortItems(detail.items, sortKey, sortDir),
    [detail.items, sortKey, sortDir]
  );

  const handleSortChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const [key, dir] = e.target.value.split(':') as [SortKey, SortDir];
    setSortKey(key);
    setSortDir(dir);
  }, []);

  return (
    <div className="collection-detail">
      <header className="collection-detail-header">
        <div className="collection-detail-title-row">
          <h2 className="collection-detail-name">{detail.name}</h2>
          <div className="collection-detail-actions">
            <button
              type="button"
              className="collection-edit-btn"
              onClick={onEdit}
              aria-label={intl.formatMessage({ id: 'collections.editCollection' })}
            >
              <Pencil size={16} aria-hidden="true" />
              {intl.formatMessage({ id: 'collections.edit' })}
            </button>
            <button
              type="button"
              className="collection-delete-btn"
              onClick={onDelete}
              aria-label={intl.formatMessage({ id: 'collections.deleteCollection' })}
            >
              <Trash2 size={16} aria-hidden="true" />
              {intl.formatMessage({ id: 'collections.delete' })}
            </button>
          </div>
        </div>
        {detail.description && <p className="collection-detail-desc">{detail.description}</p>}
      </header>

      <div className="collection-detail-toolbar">
        <span className="collection-detail-count">
          {intl.formatMessage({ id: 'collections.itemCount' }, { count: detail.items.length })}
        </span>
        <label className="collection-sort-label">
          <ArrowUpDown size={14} aria-hidden="true" />
          {intl.formatMessage({ id: 'collections.sortLabel' })}
          <select
            className="collection-sort-select"
            value={`${sortKey}:${sortDir}`}
            onChange={handleSortChange}
          >
            <option value="added_at:desc">
              {intl.formatMessage({ id: 'collections.sortNewest' })}
            </option>
            <option value="added_at:asc">
              {intl.formatMessage({ id: 'collections.sortOldest' })}
            </option>
            <option value="title:asc">
              {intl.formatMessage({ id: 'collections.sortTitleAZ' })}
            </option>
            <option value="title:desc">
              {intl.formatMessage({ id: 'collections.sortTitleZA' })}
            </option>
            <option value="author:asc">
              {intl.formatMessage({ id: 'collections.sortAuthorAZ' })}
            </option>
            <option value="year:desc">
              {intl.formatMessage({ id: 'collections.sortYearNewest' })}
            </option>
          </select>
        </label>
      </div>

      {sortedItems.length === 0 ? (
        <p className="collection-detail-empty">
          {intl.formatMessage({ id: 'collections.noItems' })}
        </p>
      ) : (
        <div className="collection-items-list">
          {sortedItems.map((item) => (
            <CollectionItemCard
              key={item.id}
              item={item}
              onRemove={onRemoveItem}
              onSaveNote={onSaveNote}
              saving={saving}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default CollectionDetailView;
