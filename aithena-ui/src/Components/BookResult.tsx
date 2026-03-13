import { BookResult } from "../hooks/search";

interface BookResultProps {
  result: BookResult;
}

/**
 * Sanitize a Solr highlight snippet so only <em> / </em> tags pass through.
 * Everything else is text-escaped to prevent XSS.
 */
function sanitizeSnippet(raw: string): string {
  return raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/&lt;em&gt;/g, "<em>")
    .replace(/&lt;\/em&gt;/g, "</em>");
}

function BookResultCard({ result }: BookResultProps) {
  const { title, author, year, snippet, category, page_count } = result;

  return (
    <div className="book-result-card">
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
