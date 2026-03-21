import { useIntl } from 'react-intl';
import { type Collection } from '../services/collectionsApi';
import { Library } from 'lucide-react';

interface CollectionsGridProps {
  collections: Collection[];
  onSelect: (id: string) => void;
}

function formatDate(iso: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
}

function CollectionsGrid({ collections, onSelect }: CollectionsGridProps) {
  const intl = useIntl();

  if (collections.length === 0) {
    return <p className="collections-empty">{intl.formatMessage({ id: 'collections.empty' })}</p>;
  }

  return (
    <div
      className="collections-grid"
      aria-label={intl.formatMessage({ id: 'collections.gridLabel' })}
    >
      {collections.map((col) => (
        <button
          key={col.id}
          className="collection-card"
          onClick={() => onSelect(col.id)}
          type="button"
        >
          <div className="collection-card-icon">
            <Library size={24} aria-hidden="true" />
          </div>
          <h3 className="collection-card-name">{col.name}</h3>
          {col.description && <p className="collection-card-desc">{col.description}</p>}
          <div className="collection-card-meta">
            <span className="collection-card-count">
              {intl.formatMessage({ id: 'collections.itemCount' }, { count: col.item_count })}
            </span>
            <span className="collection-card-updated">
              {intl.formatMessage(
                { id: 'collections.lastUpdated' },
                { date: formatDate(col.updated_at, intl.locale) }
              )}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

export default CollectionsGrid;
