import { SearchFilters } from "../hooks/search";

interface ActiveFiltersProps {
  filters: SearchFilters;
  onRemove: (key: keyof SearchFilters) => void;
  onClearAll: () => void;
}

const FILTER_LABELS: Record<keyof SearchFilters, string> = {
  author: "Author",
  category: "Category",
  language: "Language",
  year: "Year",
};

function ActiveFilters({ filters, onRemove, onClearAll }: ActiveFiltersProps) {
  const activeEntries = (
    Object.entries(filters) as [keyof SearchFilters, string | undefined][]
  ).filter(([, value]) => value !== undefined && value !== "");

  if (activeEntries.length === 0) return null;

  return (
    <div className="active-filters">
      <span className="active-filters-label">Active filters:</span>
      {activeEntries.map(([key, value]) => (
        <span key={key} className="filter-chip">
          <span className="filter-chip-label">{FILTER_LABELS[key]}:</span>
          <span className="filter-chip-value">{value}</span>
          <button
            className="filter-chip-remove"
            onClick={() => onRemove(key)}
            aria-label={`Remove ${FILTER_LABELS[key]} filter`}
          >
            ×
          </button>
        </span>
      ))}
      {activeEntries.length > 1 && (
        <button className="clear-all-filters" onClick={onClearAll}>
          Clear all
        </button>
      )}
    </div>
  );
}

export default ActiveFilters;
