import { SearchMode } from "./buildQuery";

interface QueryPreviewProps {
  mode: SearchMode;
  keywordQuery: string;
  semanticQuery: string;
}

function QueryPreview({ mode, keywordQuery, semanticQuery }: QueryPreviewProps) {
  return (
    <div className="advanced-query-preview card border-0 shadow-sm">
      <div className="card-body">
        <div className="advanced-search-section-label mb-2">Live query preview</div>
        {mode === "hybrid" ? (
          <div className="advanced-query-preview-grid">
            <div>
              <div className="advanced-search-label">Keyword clause</div>
              <code>{keywordQuery}</code>
            </div>
            <div>
              <div className="advanced-search-label">Semantic query</div>
              <code>{semanticQuery.trim() || "Enter a natural language question…"}</code>
            </div>
          </div>
        ) : (
          <code>{mode === "semantic" ? semanticQuery.trim() || "Enter a natural language question…" : keywordQuery}</code>
        )}
      </div>
    </div>
  );
}

export default QueryPreview;
