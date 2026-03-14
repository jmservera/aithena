import { BookResult } from '../hooks/search';

interface BookCardProps {
  book: BookResult;
  onOpenPdf?: (book: BookResult) => void;
  isSelected?: boolean;
}

/**
 * Sanitize Solr highlight snippets to allow only <em> tags.
 * Solr uses <em>…</em> to wrap matched terms; all other HTML is stripped.
 */
function sanitizeHighlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/&lt;em&gt;/g, '<em>')
    .replace(/&lt;\/em&gt;/g, '</em>');
}

function BookCard({ book, onOpenPdf, isSelected = false }: BookCardProps) {
  return (
    <article className={`book-card${isSelected ? ' book-card--active' : ''}`}>
      <h2 className="book-title">{book.title}</h2>
      <div className="book-meta">
        {book.author && (
          <span className="book-meta-item">
            <span className="book-meta-label">Author:</span> {book.author}
          </span>
        )}
        {book.year && (
          <span className="book-meta-item">
            <span className="book-meta-label">Year:</span> {book.year}
          </span>
        )}
        {book.category && (
          <span className="book-meta-item">
            <span className="book-meta-label">Category:</span> {book.category}
          </span>
        )}
        {book.language && (
          <span className="book-meta-item">
            <span className="book-meta-label">Language:</span> {book.language}
          </span>
        )}
        {book.page_count !== undefined && (
          <span className="book-meta-item">
            <span className="book-meta-label">Pages:</span> {book.page_count}
          </span>
        )}
      </div>
      {book.highlights && book.highlights.length > 0 && (
        <div className="book-highlights">
          {book.highlights.map((snippet, i) => (
            <p
              key={i}
              className="book-highlight-snippet"
              dangerouslySetInnerHTML={{
                __html: `\u2026${sanitizeHighlight(snippet)}\u2026`,
              }}
            />
          ))}
        </div>
      )}
      <div className="book-card-footer">
        {book.file_path && <p className="book-filepath">{book.file_path}</p>}
        {book.document_url && onOpenPdf && (
          <button
            className="open-pdf-btn"
            onClick={() => onOpenPdf(book)}
            aria-label={`Open PDF for ${book.title}`}
          >
            📄 Open PDF
          </button>
        )}
      </div>
    </article>
  );
}

export default BookCard;
