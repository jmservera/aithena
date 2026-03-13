import { BookResult } from "../hooks/search";

interface BookResultProps {
  result: BookResult;
  onSelect?: (result: BookResult) => void;
  selected?: boolean;
}

/**
 * Sanitize a Solr highlight snippet so only <em> / </em> tags pass through.
 * Solr returns raw (un-encoded) text with literal <em> highlight markers, so
 * we first escape all HTML characters, then selectively restore the <em> tags.
 * This avoids double-encoding because Solr never pre-encodes snippet content.
 */
function sanitizeSnippet(raw: string): string {
  return raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/&lt;em&gt;/g, "<em>")
    .replace(/&lt;\/em&gt;/g, "</em>");
}

function BookResultCard({ result, onSelect, selected }: BookResultProps) {
  const { title, author, year, snippet, category, page_count } = result;

  return (
    <div
      className={`book-result-card${selected ? " book-result-card--selected" : ""}${onSelect ? " book-result-card--clickable" : ""}`}
      onClick={onSelect ? () => onSelect(result) : undefined}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(result);
              }
            }
          : undefined
      }
      aria-pressed={selected}
    >
      <div className="book-result-header">
        <h3 className="book-title">{title || "Untitled"}</h3>
        <div className="book-meta">
          {author && <span className="book-author">{author}</span>}
          {year && <span className="book-year">{year}</span>}
          {category && <span className="book-category">{category}</span>}
          {page_count && (
            <span className="book-pages">{page_count} pages</span>
          )}
        </div>
      </div>
      {snippet && (
        <p
          className="book-snippet"
          dangerouslySetInnerHTML={{ __html: sanitizeSnippet(snippet) }}
        />
      )}
    </div>
  );
}

export default BookResultCard;
