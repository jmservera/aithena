import { memo, useMemo } from 'react';
import { useIntl } from 'react-intl';

import { SearchFilters } from '../hooks/search';
import FilterChip from './FilterChip';

interface ActiveFiltersProps {
  filters: SearchFilters;
  onRemove: (key: keyof SearchFilters) => void;
  onClearAll: () => void;
}

const FILTER_LABEL_KEYS: Record<keyof SearchFilters, string> = {
  author: 'filters.author',
  category: 'filters.category',
  language: 'filters.language',
  year: 'filters.year',
  series: 'filters.series',
  folder: 'filters.folder',
};

const ActiveFilters = memo(function ActiveFilters({
  filters,
  onRemove,
  onClearAll,
}: ActiveFiltersProps) {
  const intl = useIntl();
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
      <span className="active-filters-label">
        {intl.formatMessage({ id: 'filters.activeFilters' })}
      </span>
      {activeEntries.map(([key, value]) => (
        <FilterChip
          key={key}
          filterKey={key}
          label={intl.formatMessage({ id: FILTER_LABEL_KEYS[key] })}
          value={value}
          onRemove={onRemove}
        />
      ))}
      {activeEntries.length > 1 && (
        <button className="clear-all-filters" onClick={onClearAll}>
          {intl.formatMessage({ id: 'filters.clearAll' })}
        </button>
      )}
    </div>
  );
});

export default ActiveFilters;
