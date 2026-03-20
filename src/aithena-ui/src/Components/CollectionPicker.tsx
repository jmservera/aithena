import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { Search } from 'lucide-react';
import { type Collection, fetchCollections } from '../services/collectionsApi';

interface CollectionPickerProps {
  /** Called when the user selects a collection. */
  onSelect: (collectionId: string) => void;
  /** Optional: collection IDs to exclude from the list. */
  excludeIds?: string[];
}

function CollectionPicker({ onSelect, excludeIds = [] }: CollectionPickerProps) {
  const intl = useIntl();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchCollections().then((data) => {
      if (!cancelled) setCollections(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = collections.filter(
    (c) => !excludeIds.includes(c.id) && c.name.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = useCallback(
    (id: string) => {
      onSelect(id);
      setOpen(false);
      setQuery('');
    },
    [onSelect]
  );

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div className="collection-picker" ref={containerRef}>
      <button
        type="button"
        className="collection-picker-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {intl.formatMessage({ id: 'collections.addToCollection' })}
      </button>
      {open && (
        <div className="collection-picker-dropdown" role="listbox">
          <div className="collection-picker-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="text"
              className="collection-picker-input"
              placeholder={intl.formatMessage({ id: 'collections.searchCollections' })}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={intl.formatMessage({ id: 'collections.searchCollections' })}
            />
          </div>
          {filtered.length === 0 ? (
            <p className="collection-picker-empty">
              {intl.formatMessage({ id: 'collections.noCollectionsFound' })}
            </p>
          ) : (
            filtered.map((col) => (
              <button
                key={col.id}
                type="button"
                className="collection-picker-option"
                role="option"
                aria-selected={false}
                onClick={() => handleSelect(col.id)}
              >
                <span className="collection-picker-name">{col.name}</span>
                <span className="collection-picker-count">
                  {intl.formatMessage({ id: 'collections.itemCount' }, { count: col.item_count })}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default CollectionPicker;
