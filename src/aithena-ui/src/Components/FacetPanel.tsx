import { memo } from 'react';

import { FacetGroups, SearchFilters, SearchMode } from '../hooks/search';

interface FacetPanelProps {
  facets: FacetGroups;
  filters: SearchFilters;
  onFilterChange: (key: keyof SearchFilters, value: string | undefined) => void;
  mode?: SearchMode;
}

const FACET_LABELS: Record<keyof FacetGroups, string> = {
  author: 'Author',
  category: 'Category',
  language: 'Language',
  year: 'Year',
};

const FACET_KEYS = ['author', 'category', 'language', 'year'] as const;

const FacetPanel = memo(function FacetPanel({
  facets,
  filters,
  onFilterChange,
  mode,
}: FacetPanelProps) {
  return (
    <div className="facet-panel">
      {mode === 'semantic' && (
        <p className="facet-unavailable" role="note" aria-live="polite">
          Facets are only available in keyword mode
        </p>
      )}
      {mode !== 'semantic' &&
        FACET_KEYS.map((key) => {
          const values = facets[key];
          if (!values || values.length === 0) return null;
          const activeValue = filters[key];

          return (
            <div key={key} className="facet-group">
              <h3 className="facet-group-title">{FACET_LABELS[key]}</h3>
              <ul className="facet-list">
                {values.map(({ value, count }) => (
                  <li key={value} className="facet-item">
                    <label className="facet-label">
                      <input
                        type="checkbox"
                        className="facet-checkbox"
                        checked={activeValue === value}
                        onChange={() =>
                          onFilterChange(key, activeValue === value ? undefined : value)
                        }
                      />
                      <span className="facet-value">{value}</span>
                      <span className="facet-count">({count})</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
    </div>
  );
});

export default FacetPanel;
