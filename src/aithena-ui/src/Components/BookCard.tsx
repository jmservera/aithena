import { memo, useCallback, useMemo } from 'react';
import { useIntl } from 'react-intl';
import { FileText } from 'lucide-react';

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

const BookCard = memo(function BookCard({ book, onOpenPdf, isSelected = false }: BookCardProps) {
  const intl = useIntl();

  const foundPagesLabel = useMemo(() => {
    if (!book.pages) return null;
    const [pageStart, pageEnd] = book.pages;
    if (pageEnd !== pageStart) {
      return intl.formatMessage({ id: 'book.foundOnPages' }, { pageStart, pageEnd });
    }
    return intl.formatMessage({ id: 'book.foundOnPage' }, { pageStart });
  }, [book.pages, intl]);

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
            <span className="book-meta-label">{intl.formatMessage({ id: 'book.metaAuthor' })}</span>{' '}
            {book.author}
          </span>
        )}
        {book.year && (
          <span className="book-meta-item">
            <span className="book-meta-label">{intl.formatMessage({ id: 'book.metaYear' })}</span>{' '}
            {book.year}
          </span>
        )}
        {book.category && (
          <span className="book-meta-item">
            <span className="book-meta-label">
              {intl.formatMessage({ id: 'book.metaCategory' })}
            </span>{' '}
            {book.category}
          </span>
        )}
        {book.language && (
          <span className="book-meta-item">
            <span className="book-meta-label">
              {intl.formatMessage({ id: 'book.metaLanguage' })}
            </span>{' '}
            {book.language}
          </span>
        )}
        {book.series && (
          <span className="book-meta-item">
            <span className="book-meta-label">{intl.formatMessage({ id: 'book.metaSeries' })}</span>{' '}
            {book.series}
          </span>
        )}
        {book.page_count !== undefined && (
          <span className="book-meta-item">
            <span className="book-meta-label">{intl.formatMessage({ id: 'book.metaPages' })}</span>{' '}
            {book.page_count}
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
            aria-label={intl.formatMessage({ id: 'book.openPdfFor' }, { title: book.title })}
            aria-haspopup="dialog"
            aria-expanded={isSelected}
          >
            <FileText size={20} aria-hidden="true" /> {intl.formatMessage({ id: 'book.openPdf' })}
          </button>
        )}
      </div>
    </article>
  );
});

export default BookCard;
