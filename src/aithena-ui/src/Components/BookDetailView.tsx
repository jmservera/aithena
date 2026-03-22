import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { BookOpen, ExternalLink, FileText, Pencil, X } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import { useBookDetail } from '../hooks/bookDetail';
import { BookResult } from '../hooks/search';
import SimilarBooks from './SimilarBooks';

interface BookDetailViewProps {
  bookId: string;
  initialData?: BookResult;
  onClose: () => void;
  onOpenPdf: (book: BookResult) => void;
  onSelectSimilarBook: (bookId: string) => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), iframe, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function BookDetailView({
  bookId,
  initialData,
  onClose,
  onOpenPdf,
  onSelectSimilarBook,
}: BookDetailViewProps) {
  const intl = useIntl();
  const { user } = useAuth();
  const { book, loading, error } = useBookDetail(bookId, initialData);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);

  const isAdmin = user?.role === 'admin';

  // Body scroll lock + initial focus
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  // ESC to dismiss + focus trap
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== 'Tab' || !panelRef.current) {
        return;
      }

      const focusableElements = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => !el.hasAttribute('disabled'));

      if (focusableElements.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;
      const focusInsidePanel =
        activeElement instanceof HTMLElement && panelRef.current.contains(activeElement);

      if (event.shiftKey) {
        if (!focusInsidePanel || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
        return;
      }

      if (!focusInsidePanel || activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleOpenPdf = useCallback(() => {
    if (book) {
      setPdfViewerOpen(true);
      onOpenPdf(book);
    }
  }, [book, onOpenPdf]);

  const handleBackdropClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- backdrop dismiss is supplemental; ESC is the keyboard equivalent
    <div
      className="book-detail-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={handleBackdropClick}
    >
      <div ref={panelRef} className="book-detail-panel" tabIndex={-1}>
        {/* Toolbar */}
        <div className="book-detail-toolbar">
          <div className="book-detail-toolbar__title">
            <span className="book-detail-icon" aria-hidden="true">
              <BookOpen size={19} />
            </span>
            <strong id={titleId}>
              {loading
                ? intl.formatMessage({ id: 'bookDetail.loading' })
                : book?.title || intl.formatMessage({ id: 'bookDetail.untitled' })}
            </strong>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="book-detail-toolbar__btn book-detail-toolbar__btn--close"
            onClick={onClose}
            aria-label={intl.formatMessage({ id: 'bookDetail.close' })}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="book-detail-body">
          {loading ? (
            <div className="book-detail-loading" role="status" aria-live="polite">
              <div className="book-detail-skeleton book-detail-skeleton--title" />
              <div className="book-detail-skeleton book-detail-skeleton--text" />
              <div className="book-detail-skeleton book-detail-skeleton--text" />
              <div className="book-detail-skeleton book-detail-skeleton--grid" />
            </div>
          ) : error ? (
            <div className="book-detail-error" role="alert">
              <p>{intl.formatMessage({ id: 'bookDetail.error' })}</p>
              <p className="book-detail-error__detail">{error}</p>
            </div>
          ) : book ? (
            <>
              {/* Header section */}
              <div className="book-detail-header">
                <h2 className="book-detail-header__title">{book.title}</h2>
                <p className="book-detail-header__author">
                  {book.author || intl.formatMessage({ id: 'book.unknownAuthor' })}
                </p>
                {book.year && <span className="book-detail-header__year">{book.year}</span>}
              </div>

              {/* Metadata grid */}
              <div className="book-detail-meta">
                {book.category && (
                  <div className="book-detail-meta__item">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'book.metaCategory' })}
                    </span>
                    <span className="book-detail-meta__value">{book.category}</span>
                  </div>
                )}
                {book.language && (
                  <div className="book-detail-meta__item">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'book.metaLanguage' })}
                    </span>
                    <span className="book-detail-meta__value">{book.language}</span>
                  </div>
                )}
                {book.series && (
                  <div className="book-detail-meta__item">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'book.metaSeries' })}
                    </span>
                    <span className="book-detail-meta__value">{book.series}</span>
                  </div>
                )}
                {book.page_count != null && (
                  <div className="book-detail-meta__item">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'book.metaPages' })}
                    </span>
                    <span className="book-detail-meta__value">{book.page_count}</span>
                  </div>
                )}
                {book.file_size != null && (
                  <div className="book-detail-meta__item">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'bookDetail.fileSize' })}
                    </span>
                    <span className="book-detail-meta__value">
                      {formatFileSize(book.file_size)}
                    </span>
                  </div>
                )}
                {book.folder_path && (
                  <div className="book-detail-meta__item book-detail-meta__item--full">
                    <span className="book-detail-meta__label">
                      {intl.formatMessage({ id: 'bookDetail.folderPath' })}
                    </span>
                    <span className="book-detail-meta__value book-detail-meta__value--path">
                      {book.folder_path}
                    </span>
                  </div>
                )}
              </div>

              {/* Chunk text preview */}
              {book.is_chunk && book.chunk_text && (
                <div className="book-detail-chunk">
                  <h3 className="book-detail-chunk__heading">
                    {intl.formatMessage({ id: 'book.matchingText' })}
                  </h3>
                  {book.page_start != null && (
                    <span className="book-detail-chunk__pages">
                      {book.page_end != null && book.page_end !== book.page_start
                        ? intl.formatMessage(
                            { id: 'book.chunkPages' },
                            { start: book.page_start, end: book.page_end }
                          )
                        : intl.formatMessage({ id: 'book.chunkPage' }, { page: book.page_start })}
                    </span>
                  )}
                  <p className="book-detail-chunk__text">{book.chunk_text}</p>
                </div>
              )}

              {/* Action buttons */}
              <div className="book-detail-actions">
                <button
                  type="button"
                  className="book-detail-actions__btn book-detail-actions__btn--primary"
                  onClick={handleOpenPdf}
                  disabled={pdfViewerOpen}
                >
                  <FileText size={16} aria-hidden="true" />
                  {intl.formatMessage({ id: 'book.openPdf' })}
                </button>

                {book.document_url && (
                  <a
                    href={book.document_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="book-detail-actions__btn book-detail-actions__btn--secondary"
                  >
                    <ExternalLink size={16} aria-hidden="true" />
                    {intl.formatMessage({ id: 'bookDetail.openExternal' })}
                  </a>
                )}

                {isAdmin && (
                  <button
                    type="button"
                    className="book-detail-actions__btn book-detail-actions__btn--secondary"
                    aria-label={intl.formatMessage({ id: 'book.editMetadata' })}
                  >
                    <Pencil size={16} aria-hidden="true" />
                    {intl.formatMessage({ id: 'book.editMetadata' })}
                  </button>
                )}
              </div>

              {/* Similar books */}
              <div className="book-detail-similar">
                <SimilarBooks documentId={book.id} onSelectBook={onSelectSimilarBook} />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default BookDetailView;
