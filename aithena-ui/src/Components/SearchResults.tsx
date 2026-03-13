import { BookResult } from "../hooks/search";

interface SearchResultsProps {
  results: BookResult[];
  total: number;
  query: string;
  onOpenPdf: (result: BookResult) => void;
  selectedId?: string | null;
}

const SearchResults = ({
  results,
  total,
  query,
  onOpenPdf,
  selectedId = null,
}: SearchResultsProps) => {
  if (results.length === 0) return null;

  return (
    <section className="search-results" aria-label="Search results">
      <p className="search-results-summary">
        {total} result{total !== 1 ? "s" : ""} for <strong>"{query}"</strong>
      </p>
      <ul className="result-list">
        {results.map((result) => (
          <li
            key={result.id}
            className={`result-card${selectedId === result.id ? " result-card--active" : ""}`}
          >
            <div className="result-meta">
              <span className="result-score" title="Relevance score">
                {Math.round(result.score * 100)}%
              </span>
              <h3 className="result-title">{result.title || "Untitled"}</h3>
              {result.author && (
                <p className="result-author">{result.author}</p>
              )}
              {result.page != null && (
                <p className="result-page">Page {result.page}</p>
              )}
            </div>
            {result.snippet && (
              <p className="result-snippet">{result.snippet}</p>
            )}
            <div className="result-actions">
              {result.document_url ? (
                <button
                  className="open-pdf-button"
                  onClick={() => onOpenPdf(result)}
                  aria-label={`Open PDF for ${result.title || "this document"}`}
                >
                  📄 Open PDF
                </button>
              ) : (
                <span className="no-pdf-label">No PDF available</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default SearchResults;
