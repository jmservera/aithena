import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { FileText } from 'lucide-react';

import { BookResult } from '../hooks/search';
import CollectionBadge from './CollectionBadge';

interface BookCardProps {
  book: BookResult;
  onOpenPdf?: (book: BookResult) => void;
  isSelected?: boolean;
  isAdmin?: boolean;
  onEditMetadata?: (book: BookResult) => void;
  onSaveToCollection?: (book: BookResult) => void;
  selectionMode?: boolean;
  isChecked?: boolean;
  onToggleSelect?: (id: string) => void;
}

function sanitizeHighlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/&lt;em&gt;/g, '<em>')
    .replace(/&lt;\/em&gt;/g, '</em>');
}

const BookCard = memo(function BookCard({
  book,
  onOpenPdf,
  isSelected = false,
  isAdmin = false,
  onEditMetadata,
  onSaveToCollection,
  selectionMode = false,
  isChecked = false,
  onToggleSelect,
}: BookCardProps) {
  const intl = useIntl();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const showMenu = (isAdmin && onEditMetadata) || onSaveToCollection;

  const handleToggleMenu = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

  const handleEditMetadata = useCallback(() => {
    setMenuOpen(false);
    onEditMetadata?.(book);
  }, [book, onEditMetadata]);

  const handleSaveToCollection = useCallback(() => {
    setMenuOpen(false);
    onSaveToCollection?.(book);
  }, [book, onSaveToCollection]);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

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

  const handleToggleSelect = useCallback(() => {
    onToggleSelect?.(book.id);
  }, [book.id, onToggleSelect]);

  return (
    <article className={`book-card${isSelected ? ' book-card--active' : ''}`}>
      <div className="book-card-header">
        {selectionMode && (
          <div className="book-card-select-checkbox">
            <input
              type="checkbox"
              checked={isChecked}
              onChange={handleToggleSelect}
              aria-label={intl.formatMessage({ id: 'book.selectBook' }, { title: book.title })}
            />
          </div>
        )}
        <h2 className="book-title">{book.title}</h2>
        {book.in_collections != null && book.in_collections > 0 && (
          <CollectionBadge count={book.in_collections} />
        )}
        {showMenu && (
          <div className="book-card-menu-wrapper" ref={menuRef}>
            <button
              type="button"
              className="book-card-menu-btn"
              onClick={handleToggleMenu}
              aria-label={intl.formatMessage({ id: 'book.menuToggle' }, { title: book.title })}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              ⋮
            </button>
            {menuOpen && (
              <ul className="book-card-menu" role="menu">
                {isAdmin && onEditMetadata && (
                  <li role="none">
                    <button
                      type="button"
                      role="menuitem"
                      className="book-card-menu-item"
                      onClick={handleEditMetadata}
                    >
                      {intl.formatMessage({ id: 'book.editMetadata' })}
                    </button>
                  </li>
                )}
                {onSaveToCollection && (
                  <li role="none">
                    <button
                      type="button"
                      role="menuitem"
                      className="book-card-menu-item"
                      onClick={handleSaveToCollection}
                    >
                      {intl.formatMessage({ id: 'collections.saveToCollection' })}
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>
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
