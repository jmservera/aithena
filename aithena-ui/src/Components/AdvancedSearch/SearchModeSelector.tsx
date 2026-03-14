import { SearchMode } from "./buildQuery";

interface SearchModeSelectorProps {
  mode: SearchMode;
  enabledModes: SearchMode[];
  onChange: (mode: SearchMode) => void;
}

const SEARCH_MODE_OPTIONS: Array<{
  value: SearchMode;
  label: string;
  description: string;
}> = [
  { value: "keyword", label: "Keyword", description: "Structured Solr query builder" },
  { value: "semantic", label: "Semantic", description: "Natural language search" },
  { value: "hybrid", label: "Hybrid", description: "Keyword + semantic search" },
];

function SearchModeSelector({ mode, enabledModes, onChange }: SearchModeSelectorProps) {
  return (
    <div>
      <div className="advanced-search-section-label">Search mode</div>
      <div className="nav nav-tabs advanced-search-tabs" role="tablist" aria-label="Search mode selector">
        {SEARCH_MODE_OPTIONS.map((option) => {
          const isEnabled = enabledModes.includes(option.value);
          const isActive = mode === option.value;

          return (
            <button
              key={option.value}
              type="button"
              role="tab"
              className={`nav-link${isActive ? " active" : ""}`}
              aria-selected={isActive}
              onClick={() => onChange(option.value)}
              disabled={!isEnabled}
              title={!isEnabled ? `${option.label} mode will be enabled when the backend endpoint is ready.` : option.description}
            >
              <span>{option.label}</span>
              {!isEnabled && <span className="badge text-bg-secondary ms-2">Soon</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default SearchModeSelector;
