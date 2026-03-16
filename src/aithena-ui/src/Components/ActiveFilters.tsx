import { memo, useMemo } from 'react';

import { SearchFilters } from '../hooks/search';
import FilterChip from './FilterChip';

interface ActiveFiltersProps {
  filters: SearchFilters;
  onRemove: (key: keyof SearchFilters) => void;
  onClearAll: () => void;
}

const FILTER_LABELS: Record<keyof SearchFilters, string> = {
  author: 'Author',
  category: 'Category',
  language: 'Language',
  year: 'Year',
};

const ActiveFilters = memo(function ActiveFilters({
  filters,
  onRemove,
  onClearAll,
}: ActiveFiltersProps) {
  const activeEntries = useMemo(
    () =>
      (Object.entries(filters) as [keyof SearchFilters, string | undefined][]).filter(
        (entry): entry is [keyof SearchFilters, string] => {
          const [, value] = entry;
          return value !== undefined && value !== '';
        }
      ),
    [filters]
  );

  if (activeEntries.length === 0) return null;

  return (
    <div className="active-filters">
      <span className="active-filters-label">Active filters:</span>
      {activeEntries.map(([key, value]) => (
        <FilterChip
          key={key}
          filterKey={key}
          label={FILTER_LABELS[key]}
          value={value}
          onRemove={onRemove}
        />
      ))}
      {activeEntries.length > 1 && (
        <button className="clear-all-filters" onClick={onClearAll}>
          Clear all
        </button>
      )}
    </div>
  );
});

export default ActiveFilters;
