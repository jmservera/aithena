import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { BookOpen, ExternalLink, FileText, Pencil, X } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import { useBookDetail } from '../hooks/bookDetail';
import { BookResult } from '../hooks/search';
import { useMetadataEdit, MetadataFormValues } from '../hooks/useMetadataEdit';
import SimilarBooks from './SimilarBooks';

function DetailThumbnail({ src, alt }: { src: string; alt: string }) {
  const [error, setError] = useState(false);

  if (error) {
    return (
      <div
        className="book-detail-header__thumbnail book-detail-header__thumbnail--placeholder"
        aria-hidden="true"
      >
        <FileText size={64} />
      </div>
    );
  }

  return (
    <img
      className="book-detail-header__thumbnail"
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setError(true)}
    />
  );
}

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

/* ── Inline edit form sub-components ───────────────────────────── */

interface InlineTextFieldProps {
  id: string;
  label: string;
  value: string;
  maxLength: number;
  error?: string;
  onChange: (value: string) => void;
}

function InlineTextField({ id, label, value, maxLength, error, onChange }: InlineTextFieldProps) {
  return (
    <div className="meta-edit-field">
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <input
        id={id}
        type="text"
        className={`meta-edit-input${error ? ' meta-edit-input--error' : ''}`}
        value={value}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

interface InlineYearFieldProps {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}

function InlineYearField({ id, label, value, error, onChange }: InlineYearFieldProps) {
  return (
    <div className="meta-edit-field">
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <input
        id={id}
        type="number"
        className={`meta-edit-input meta-edit-input--year${error ? ' meta-edit-input--error' : ''}`}
        value={value}
        min={1000}
        max={2099}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

interface InlineComboboxFieldProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  maxLength: number;
  error?: string;
  onChange: (value: string) => void;
}

function InlineComboboxField({
  id,
  label,
  value,
  options,
  maxLength,
  error,
  onChange,
}: InlineComboboxFieldProps) {
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listboxId = `${id}-listbox`;

  const filtered = useMemo(
    () =>
      value.trim() ? options.filter((o) => o.toLowerCase().includes(value.toLowerCase())) : options,
    [options, value]
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHighlightIndex(-1);
  }, [filtered.length]);

  const selectOption = useCallback(
    (option: string) => {
      onChange(option);
      setOpen(false);
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        setOpen(true);
        e.preventDefault();
        return;
      }
      if (!open) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : 0));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIndex((prev) => (prev > 0 ? prev - 1 : filtered.length - 1));
      } else if ((e.key === 'Enter' || e.key === 'Tab') && highlightIndex >= 0) {
        e.preventDefault();
        selectOption(filtered[highlightIndex]);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    },
    [open, filtered, highlightIndex, selectOption]
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="meta-edit-field" ref={wrapperRef}>
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <div className="meta-edit-combobox-wrapper">
        <input
          id={id}
          type="text"
          role="combobox"
          className={`meta-edit-input${error ? ' meta-edit-input--error' : ''}`}
          value={value}
          maxLength={maxLength}
          autoComplete="off"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={highlightIndex >= 0 ? `${id}-option-${highlightIndex}` : undefined}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {open && filtered.length > 0 && (
          <ul id={listboxId} className="meta-edit-listbox" role="listbox">
            {filtered.map((option, idx) => (
              <li
                key={option}
                id={`${id}-option-${idx}`}
                role="option"
                className={`meta-edit-option${idx === highlightIndex ? ' meta-edit-option--active' : ''}`}
                aria-selected={idx === highlightIndex}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option);
                }}
                onMouseEnter={() => setHighlightIndex(idx)}
              >
                {option}
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/* ── Inline edit form ──────────────────────────────────────────── */

interface InlineEditFormProps {
  book: BookResult;
  onSaved: (updated: BookResult) => void;
  onCancel: () => void;
}

function InlineEditForm({ book, onSaved, onCancel }: InlineEditFormProps) {
  const intl = useIntl();
  const [toast, setToast] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleSaved = useCallback(
    (updated: BookResult) => {
      setToast(true);
      setTimeout(() => {
        if (mountedRef.current) {
          onSaved(updated);
        }
      }, 600);
    },
    [onSaved]
  );

  const { values, errors, saving, apiError, changed, facetOptions, setField, save } =
    useMetadataEdit(book, handleSaved);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      void save();
    },
    [save]
  );

  return (
    <div className="book-detail-edit">
      {toast && (
        <div className="meta-edit-toast" role="status" aria-live="polite">
          {intl.formatMessage({ id: 'metadataEdit.success' })}
        </div>
      )}

      {apiError && (
        <div className="meta-edit-api-error" role="alert">
          {apiError}
        </div>
      )}

      <form className="meta-edit-form" onSubmit={handleSubmit} noValidate>
        <InlineTextField
          id="book-detail-edit-title"
          label={intl.formatMessage({ id: 'metadataEdit.fieldTitle' })}
          value={values.title}
          maxLength={255}
          error={errors.title}
          onChange={(v: string) => setField('title' as keyof MetadataFormValues, v)}
        />
        <InlineTextField
          id="book-detail-edit-author"
          label={intl.formatMessage({ id: 'metadataEdit.fieldAuthor' })}
          value={values.author}
          maxLength={255}
          error={errors.author}
          onChange={(v: string) => setField('author' as keyof MetadataFormValues, v)}
        />
        <InlineYearField
          id="book-detail-edit-year"
          label={intl.formatMessage({ id: 'metadataEdit.fieldYear' })}
          value={values.year}
          error={errors.year}
          onChange={(v: string) => setField('year' as keyof MetadataFormValues, v)}
        />
        <InlineComboboxField
          id="book-detail-edit-category"
          label={intl.formatMessage({ id: 'metadataEdit.fieldCategory' })}
          value={values.category}
          options={facetOptions.category}
          maxLength={100}
          error={errors.category}
          onChange={(v: string) => setField('category' as keyof MetadataFormValues, v)}
        />
        <InlineComboboxField
          id="book-detail-edit-series"
          label={intl.formatMessage({ id: 'metadataEdit.fieldSeries' })}
          value={values.series}
          options={facetOptions.series}
          maxLength={100}
          error={errors.series}
          onChange={(v: string) => setField('series' as keyof MetadataFormValues, v)}
        />

        <div className="book-detail-edit__actions">
          <button
            type="button"
            className="book-detail-actions__btn book-detail-actions__btn--secondary"
            onClick={onCancel}
            disabled={saving}
          >
            {intl.formatMessage({ id: 'metadataEdit.cancel' })}
          </button>
          <button
            type="submit"
            className="book-detail-actions__btn book-detail-actions__btn--primary"
            disabled={!changed || saving}
          >
            {saving
              ? intl.formatMessage({ id: 'metadataEdit.saving' })
              : intl.formatMessage({ id: 'metadataEdit.save' })}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────── */

function BookDetailView({
  bookId,
  initialData,
  onClose,
  onOpenPdf,
  onSelectSimilarBook,
}: BookDetailViewProps) {
  const intl = useIntl();
  const { user } = useAuth();
  const { book, loading, error, refresh } = useBookDetail(bookId, initialData);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);

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
        if (editMode) {
          setEditMode(false);
        } else {
          onClose();
        }
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
  }, [onClose, editMode]);

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

  const handleEditClick = useCallback(() => {
    setEditMode(true);
  }, []);

  const handleEditCancel = useCallback(() => {
    setEditMode(false);
  }, []);

  const handleEditSaved = useCallback(() => {
    setEditMode(false);
    refresh();
  }, [refresh]);

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
              {editMode ? (
                <InlineEditForm book={book} onSaved={handleEditSaved} onCancel={handleEditCancel} />
              ) : (
                <>
                  {/* Header section */}
                  <div className="book-detail-header">
                    {book.thumbnail_url ? (
                      <DetailThumbnail src={book.thumbnail_url} alt={book.title} />
                    ) : (
                      <div
                        className="book-detail-header__thumbnail book-detail-header__thumbnail--placeholder"
                        aria-hidden="true"
                      >
                        <FileText size={64} />
                      </div>
                    )}
                    <div className="book-detail-header__info">
                      <h2 className="book-detail-header__title">{book.title}</h2>
                      <p className="book-detail-header__author">
                        {book.author || intl.formatMessage({ id: 'book.unknownAuthor' })}
                      </p>
                      {book.year && <span className="book-detail-header__year">{book.year}</span>}
                    </div>
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
                            : intl.formatMessage(
                                { id: 'book.chunkPage' },
                                { page: book.page_start }
                              )}
                        </span>
                      )}
                      <p className="book-detail-chunk__text">{book.chunk_text}</p>
                    </div>
                  )}
                </>
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

                {isAdmin && !editMode && (
                  <button
                    type="button"
                    className="book-detail-actions__btn book-detail-actions__btn--secondary"
                    onClick={handleEditClick}
                    aria-label={intl.formatMessage({ id: 'book.editMetadata' })}
                  >
                    <Pencil size={16} aria-hidden="true" />
                    {intl.formatMessage({ id: 'book.editMetadata' })}
                  </button>
                )}
              </div>

              {/* Similar books */}
              <div className="book-detail-similar">
                <SimilarBooks
                  documentId={book.parent_id || book.id}
                  onSelectBook={onSelectSimilarBook}
                />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default BookDetailView;
