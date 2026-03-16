import { memo, useCallback } from 'react';

import { SearchFilters } from '../hooks/search';

interface FilterChipProps {
  filterKey: keyof SearchFilters;
  label: string;
  value: string;
  onRemove: (key: keyof SearchFilters) => void;
}

const FilterChip = memo(function FilterChip({
  filterKey,
  label,
  value,
  onRemove,
}: FilterChipProps) {
  const handleRemove = useCallback(() => {
    onRemove(filterKey);
  }, [filterKey, onRemove]);

  return (
    <span className="filter-chip">
      <span className="filter-chip-label">{label}:</span>
      <span className="filter-chip-value">{value}</span>
      <button
        className="filter-chip-remove"
        onClick={handleRemove}
        aria-label={`Remove ${label} filter`}
      >
        ×
      </button>
    </span>
  );
});

export default FilterChip;
