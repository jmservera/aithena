import { FacetGroups, SearchFilters } from '../hooks/search';

interface FacetPanelProps {
  facets: FacetGroups;
  filters: SearchFilters;
  onFilterChange: (key: keyof SearchFilters, value: string | undefined) => void;
}

const FACET_LABELS: Record<keyof FacetGroups, string> = {
  author: 'Author',
  category: 'Category',
  language: 'Language',
  year: 'Year',
};

const FACET_KEYS = ['author', 'category', 'language', 'year'] as const;

function FacetPanel({ facets, filters, onFilterChange }: FacetPanelProps) {
  return (
    <div className="facet-panel">
      {FACET_KEYS.map((key) => {
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
}

export default FacetPanel;
