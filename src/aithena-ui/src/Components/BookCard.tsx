import { memo, useCallback, useMemo } from 'react';

import { BookResult } from '../hooks/search';

interface BookCardProps {
  book: BookResult;
  onOpenPdf?: (book: BookResult) => void;
  isSelected?: boolean;
}

function sanitizeHighlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/&lt;em&gt;/g, '<em>')
    .replace(/&lt;\/em&gt;/g, '</em>');
}

function formatFoundPages(pageStart: number, pageEnd: number): string {
  if (pageEnd !== pageStart) {
    return `Found on pages ${pageStart}–${pageEnd}`;
  }
  return `Found on page ${pageStart}`;
}

const BookCard = memo(function BookCard({ book, onOpenPdf, isSelected = false }: BookCardProps) {
  const foundPagesLabel = useMemo(
    () => (book.pages ? formatFoundPages(book.pages[0], book.pages[1]) : null),
    [book.pages]
  );
  const highlightMarkup = useMemo(
    () =>
      book.highlights?.map((snippet, index) => ({
        id: `${book.id}-highlight-${index}`,
        html: `…${sanitizeHighlight(snippet)}…`,
      })) ?? [],
    [book.highlights, book.id]
  );
  const handleOpenPdf = useCallback(() => {
    onOpenPdf?.(book);
  }, [book, onOpenPdf]);

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
        {foundPagesLabel && (
          <span className="book-meta-item book-found-pages">{foundPagesLabel}</span>
        )}
      </div>
      {highlightMarkup.length > 0 && (
        <div className="book-highlights">
          {highlightMarkup.map((snippet) => (
            <p
              key={snippet.id}
              className="book-highlight-snippet"
              dangerouslySetInnerHTML={{
                __html: snippet.html,
              }}
            />
          ))}
        </div>
      )}
      <div className="book-card-footer">
        {book.file_path && <p className="book-filepath">{book.file_path}</p>}
        {book.document_url && onOpenPdf && (
          <button
            type="button"
            className="open-pdf-btn"
            onClick={handleOpenPdf}
            aria-label={`Open PDF for ${book.title}`}
            aria-haspopup="dialog"
            aria-expanded={isSelected}
          >
            📄 Open PDF
          </button>
        )}
      </div>
    </article>
  );
});

export default BookCard;
