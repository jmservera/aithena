import { memo, useCallback, useMemo } from 'react';
import { useIntl } from 'react-intl';

import { FacetGroups, SearchFilters, SearchMode } from '../hooks/search';
import { buildFacetTree } from '../utils/buildFacetTree';
import FolderFacetTree from './FolderFacetTree';

interface FacetPanelProps {
  facets: FacetGroups;
  filters: SearchFilters;
  onFilterChange: (key: keyof SearchFilters, value: string | undefined) => void;
  mode?: SearchMode;
}

const FACET_LABEL_KEYS: Record<string, string> = {
  author: 'filters.author',
  category: 'filters.category',
  language: 'filters.language',
  year: 'filters.year',
  series: 'filters.series',
  folder: 'filters.folder',
};

const FACET_KEYS = ['author', 'category', 'language', 'year', 'series'] as const;

const FacetPanel = memo(function FacetPanel({
  facets,
  filters,
  onFilterChange,
  mode,
}: FacetPanelProps) {
  const intl = useIntl();

  const folderTree = useMemo(() => buildFacetTree(facets.folder ?? []), [facets.folder]);

  const selectedFolderPaths = useMemo(() => {
    const raw = filters.folder;
    if (!raw) return new Set<string>();
    return new Set(raw.split(',').filter(Boolean));
  }, [filters.folder]);

  const handleToggleFolderPath = useCallback(
    (fullPath: string) => {
      const next = new Set(selectedFolderPaths);
      if (next.has(fullPath)) {
        next.delete(fullPath);
      } else {
        next.add(fullPath);
      }
      const joined = [...next].join(',');
      onFilterChange('folder', joined || undefined);
    },
    [selectedFolderPaths, onFilterChange]
  );

  return (
    <div className="facet-panel">
      {mode === 'semantic' && (
        <p className="facet-unavailable" role="note" aria-live="polite">
          {intl.formatMessage({ id: 'filters.semanticUnavailable' })}
        </p>
      )}
      {mode !== 'semantic' && (
        <>
          <FolderFacetTree
            roots={folderTree}
            selectedPaths={selectedFolderPaths}
            onTogglePath={handleToggleFolderPath}
          />
          {FACET_KEYS.map((key) => {
            const values = facets[key];
            if (!values || values.length === 0) return null;
            const activeValue = filters[key];

            return (
              <div key={key} className="facet-group">
                <h3 className="facet-group-title">
                  {intl.formatMessage({ id: FACET_LABEL_KEYS[key] })}
                </h3>
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
        </>
      )}
    </div>
  );
});

export default FacetPanel;
