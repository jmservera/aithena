import {
  FormEvent,
  Profiler,
  RefObject,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { useIntl, FormattedMessage } from 'react-intl';
import { AlertTriangle, CheckSquare, Loader2 } from 'lucide-react';
import ErrorBoundary, { ErrorBoundaryFallbackProps } from '../Components/ErrorBoundary';
import FacetPanel from '../Components/FacetPanel';
import ActiveFilters from '../Components/ActiveFilters';
import BookCard from '../Components/BookCard';
import Pagination from '../Components/Pagination';
import PdfViewer from '../Components/PdfViewer';
import SimilarBooks from '../Components/SimilarBooks';
import SkeletonCard from '../Components/SkeletonCard';
import SkeletonFacetPanel from '../Components/SkeletonFacetPanel';
import AddToCollectionModal from '../Components/AddToCollectionModal';
import { SearchFilters } from '../hooks/search';
import { getCachedSimilarBook } from '../hooks/similarBooks';
import { useSearch, BookResult, SearchMode } from '../hooks/search';
import { onRenderCallback } from '../utils/profiler';
import { useToast } from '../contexts/ToastContext';

const SORT_OPTIONS = [
  { value: 'score desc', labelId: 'search.sortRelevance' },
  { value: 'year_i desc', labelId: 'search.sortYearNewest' },
  { value: 'year_i asc', labelId: 'search.sortYearOldest' },
  { value: 'title_s asc', labelId: 'search.sortTitleAZ' },
  { value: 'author_s asc', labelId: 'search.sortAuthorAZ' },
];

const MODE_OPTIONS: { value: SearchMode; labelId: string; titleId: string }[] = [
  { value: 'keyword', labelId: 'search.modeKeyword', titleId: 'search.modeKeywordTitle' },
  { value: 'semantic', labelId: 'search.modeSemantic', titleId: 'search.modeSemanticTitle' },
  { value: 'hybrid', labelId: 'search.modeHybrid', titleId: 'search.modeHybridTitle' },
];

const MODE_BADGE_CLASS: Record<SearchMode, string> = {
  keyword: 'mode-badge--keyword',
  semantic: 'mode-badge--semantic',
  hybrid: 'mode-badge--hybrid',
};

interface SearchResultsSectionProps {
  error: string | null;
  hasActiveFilters: boolean;
  loading: boolean;
  page: number;
  limit: number;
  query: string;
  results: BookResult[];
  resultsRegionId: string;
  resultsRegionRef: RefObject<HTMLElement | null>;
  resultsSummaryId: string;
  selectedBook: BookResult | null;
  total: number;
  onOpenPdf: (book: BookResult) => void;
  onPageChange: (page: number) => void;
  onPdfClose: () => void;
  onSelectSimilarBook: (bookId: string) => void;
  selectionMode?: boolean;
  checkedIds?: Set<string>;
  onToggleSelect?: (bookId: string) => void;
  onSaveToCollection?: (book: BookResult) => void;
}

function renderSearchResultsFallback({ reset, reload }: ErrorBoundaryFallbackProps) {
  return (
    <section className="error-boundary error-boundary--section" role="alert" aria-live="assertive">
      <h2 className="error-boundary__title error-boundary__title--section">
        <FormattedMessage id="search.errorTitle" />
      </h2>
      <p className="error-boundary__message">
        <FormattedMessage id="search.errorMessage" />
      </p>
      <div className="error-boundary__actions">
        <button type="button" className="error-boundary__button" onClick={reset}>
          <FormattedMessage id="search.errorRetry" />
        </button>
        <button
          type="button"
          className="error-boundary__button error-boundary__button--secondary"
          onClick={reload}
        >
          <FormattedMessage id="search.errorReload" />
        </button>
      </div>
    </section>
  );
}

function SearchResultsSection({
  error,
  hasActiveFilters,
  loading,
  page,
  limit,
  query,
  results,
  resultsRegionId,
  resultsRegionRef,
  resultsSummaryId,
  selectedBook,
  total,
  onOpenPdf,
  onPageChange,
  onPdfClose,
  onSelectSimilarBook,
  selectionMode,
  checkedIds,
  onToggleSelect,
  onSaveToCollection,
}: SearchResultsSectionProps) {
  const intl = useIntl();
  const totalPages = Math.ceil(total / limit);
  const resultsHeadingId = `${resultsRegionId}-heading`;

  return (
    <>
      <section
        id={resultsRegionId}
        ref={resultsRegionRef}
        className="search-results"
        aria-labelledby={resultsHeadingId}
        aria-describedby={query ? resultsSummaryId : undefined}
        aria-busy={loading}
        tabIndex={-1}
      >
        <h2 id={resultsHeadingId} className="visually-hidden">
          {intl.formatMessage({ id: 'search.resultsHeading' })}
        </h2>

        {error && (
          <div className="search-error" role="alert">
            <AlertTriangle size={20} aria-hidden="true" /> {error}
          </div>
        )}

        {!loading && !error && !query && (
          <div className="search-empty">{intl.formatMessage({ id: 'search.emptyPrompt' })}</div>
        )}

        {!loading && !error && query && results.length === 0 && (
          <div className="search-empty">
            {hasActiveFilters
              ? intl.formatMessage({ id: 'search.noResultsFiltered' }, { query })
              : intl.formatMessage({ id: 'search.noResults' }, { query })}
          </div>
        )}

        {loading && query && (
          <ul className="search-results-list">
            <SkeletonCard count={limit || 10} />
          </ul>
        )}

        {!loading && results.length > 0 && (
          <ul className="search-results-list">
            {results.map((book) => (
              <li key={book.id} className="search-results-item">
                <BookCard
                  book={book}
                  onOpenPdf={onOpenPdf}
                  isSelected={selectedBook?.id === book.id}
                  selectionMode={selectionMode}
                  isChecked={checkedIds?.has(book.id)}
                  onToggleSelect={onToggleSelect}
                  onSaveToCollection={onSaveToCollection}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {selectedBook && (
        <SimilarBooks documentId={selectedBook.id} onSelectBook={onSelectSimilarBook} />
      )}

      {total > 0 && (
        <footer className="search-footer">
          <Pagination
            page={page}
            limit={limit}
            total={total}
            onPageChange={onPageChange}
            controlsId={resultsRegionId}
          />
          <p className="pagination-info">
            {intl.formatMessage({ id: 'search.pageInfo' }, { page, totalPages })}
          </p>
        </footer>
      )}

      {selectedBook && <PdfViewer result={selectedBook} onClose={onPdfClose} />}
    </>
  );
}

function SearchPage() {
  const intl = useIntl();
  const { addToast } = useToast();
  const {
    searchState,
    results,
    facets,
    total,
    loading,
    error,
    setQuery,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
    setMode,
  } = useSearch();

  // Keep the text input in sync with the committed query from the URL so
  // that deep-links and browser back / forward reflect the correct value.
  const [inputValue, setInputValue] = useState(searchState.query);

  // Sync input value when URL query changes (e.g., browser back/forward)
  // This is a legitimate controlled input pattern
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInputValue(searchState.query);
  }, [searchState.query]);

  const [selectedBook, setSelectedBook] = useState<BookResult | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [addToCollectionOpen, setAddToCollectionOpen] = useState(false);
  const [addToCollectionDocIds, setAddToCollectionDocIds] = useState<string[]>([]);
  const resultsRegionRef = useRef<HTMLElement>(null);
  const lastLoadingStateRef = useRef(false);
  const lastPdfTriggerRef = useRef<HTMLElement | null>(null);
  const searchInputId = useId();
  const resultsRegionId = useId();
  const resultsSummaryId = useId();

  useEffect(() => {
    if (searchState.query && lastLoadingStateRef.current && !loading) {
      resultsRegionRef.current?.focus();
    }

    lastLoadingStateRef.current = loading;
  }, [loading, searchState.query]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setQuery(inputValue.trim());
  }

  function handleRemoveFilter(key: keyof SearchFilters) {
    setFilter(key, undefined);
  }

  const hasActiveFilters = Object.values(searchState.filters).some(
    (value) => value !== undefined && value !== ''
  );

  const handleOpenPdf = useCallback((book: BookResult) => {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement) {
      lastPdfTriggerRef.current = activeElement;
    }

    setSelectedBook(book);
  }, []);

  const handleClosePdf = useCallback(() => {
    setSelectedBook(null);

    window.requestAnimationFrame(() => {
      lastPdfTriggerRef.current?.focus();
    });
  }, []);

  const handleSelectSimilarBook = useCallback(
    (bookId: string) => {
      const activeElement = document.activeElement;
      if (activeElement instanceof HTMLElement) {
        lastPdfTriggerRef.current = activeElement;
      }

      const similarBook = getCachedSimilarBook(bookId);
      const searchResult = results.find((book) => book.id === bookId);

      setSelectedBook((currentBook) => similarBook ?? searchResult ?? currentBook);
    },
    [results]
  );

  const handleToggleSelectionMode = useCallback(() => {
    setSelectionMode((prev) => {
      if (prev) setCheckedIds(new Set());
      return !prev;
    });
  }, []);

  const handleToggleSelect = useCallback((bookId: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(bookId)) next.delete(bookId);
      else next.add(bookId);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setCheckedIds(new Set(results.map((b) => b.id)));
  }, [results]);

  const handleDeselectAll = useCallback(() => {
    setCheckedIds(new Set());
  }, []);

  const handleSaveToCollection = useCallback((book: BookResult) => {
    setAddToCollectionDocIds([book.id]);
    setAddToCollectionOpen(true);
  }, []);

  const handleBulkAddToCollection = useCallback(() => {
    if (checkedIds.size === 0) return;
    setAddToCollectionDocIds([...checkedIds]);
    setAddToCollectionOpen(true);
  }, [checkedIds]);

  const handleAddToCollectionSuccess = useCallback(
    (collectionName: string, count: number) => {
      addToast(
        intl.formatMessage({ id: 'collections.addedToast' }, { name: collectionName, count }),
        'success'
      );
      setCheckedIds(new Set());
      setSelectionMode(false);
    },
    [addToast, intl]
  );

  const handleAddToCollectionClose = useCallback(() => {
    setAddToCollectionOpen(false);
    setAddToCollectionDocIds([]);
  }, []);

  return (
    <div className="search-layout">
      <aside className="sidebar">
        {loading && !searchState.query ? (
          <SkeletonFacetPanel />
        ) : (
          <FacetPanel
            facets={facets}
            filters={searchState.filters}
            onFilterChange={setFilter}
            mode={searchState.mode}
          />
        )}
      </aside>

      <main className="search-main">
        <header className="search-header">
          <form
            className="search-form"
            role="search"
            aria-label={intl.formatMessage({ id: 'search.formLabel' })}
            onSubmit={handleSubmit}
          >
            <label className="visually-hidden" htmlFor={searchInputId}>
              {intl.formatMessage({ id: 'search.inputLabel' })}
            </label>
            <input
              id={searchInputId}
              className="search-input"
              type="search"
              value={inputValue}
              placeholder={intl.formatMessage({ id: 'search.placeholder' })}
              onChange={(event) => setInputValue(event.target.value)}
              aria-label={intl.formatMessage({ id: 'search.inputAriaLabel' })}
            />
            <button className="search-btn" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 size={16} className="spinner" aria-hidden="true" />
                  {intl.formatMessage({ id: 'search.searching' })}
                </>
              ) : (
                intl.formatMessage({ id: 'search.button' })
              )}
            </button>
          </form>

          <div
            className="mode-selector"
            role="group"
            aria-label={intl.formatMessage({ id: 'search.modeGroupLabel' })}
          >
            {MODE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`mode-btn${searchState.mode === option.value ? ' mode-btn--active' : ''}`}
                onClick={() => setMode(option.value)}
                title={intl.formatMessage({ id: option.titleId })}
                aria-pressed={searchState.mode === option.value}
              >
                {intl.formatMessage({ id: option.labelId })}
              </button>
            ))}
          </div>

          {searchState.query && (
            <div className="search-controls">
              <p
                id={resultsSummaryId}
                className="search-result-count"
                role="status"
                aria-live="polite"
                aria-atomic="true"
              >
                {loading ? (
                  intl.formatMessage({ id: 'search.searching' })
                ) : (
                  <>
                    {intl.formatMessage(
                      { id: 'search.resultCount' },
                      { total, query: searchState.query }
                    )}
                    <span
                      className={`mode-badge ${MODE_BADGE_CLASS[searchState.mode]}`}
                      title={intl.formatMessage(
                        { id: 'search.modeLabel' },
                        { mode: searchState.mode }
                      )}
                      aria-label={intl.formatMessage(
                        { id: 'search.modeLabel' },
                        { mode: searchState.mode }
                      )}
                    >
                      {searchState.mode}
                    </span>
                  </>
                )}
              </p>
              <div className="search-sort-limit">
                <label htmlFor="sort-select" className="control-label">
                  {intl.formatMessage({ id: 'search.sortLabel' })}
                </label>
                <select
                  id="sort-select"
                  className="sort-select"
                  value={searchState.sort}
                  onChange={(event) => setSort(event.target.value)}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {intl.formatMessage({ id: option.labelId })}
                    </option>
                  ))}
                </select>

                <label htmlFor="limit-select" className="control-label">
                  {intl.formatMessage({ id: 'search.perPageLabel' })}
                </label>
                <select
                  id="limit-select"
                  className="sort-select"
                  value={searchState.limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                >
                  {[10, 20, 50].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {hasActiveFilters && (
            <ActiveFilters
              filters={searchState.filters}
              onRemove={handleRemoveFilter}
              onClearAll={clearFilters}
            />
          )}

          {searchState.query && !loading && results.length > 0 && (
            <div className="batch-select-all-bar">
              <button
                type="button"
                className={`batch-select-mode-btn${selectionMode ? ' batch-select-mode-btn--active' : ''}`}
                onClick={handleToggleSelectionMode}
                aria-pressed={selectionMode}
                title={intl.formatMessage({ id: 'search.multiSelectTitle' })}
              >
                <CheckSquare size={16} aria-hidden="true" />{' '}
                {intl.formatMessage({ id: 'search.multiSelect' })}
              </button>
              {selectionMode && (
                <>
                  <button type="button" className="batch-select-all-btn" onClick={handleSelectAll}>
                    {intl.formatMessage({ id: 'batchEdit.selectAll' })}
                  </button>
                  <button
                    type="button"
                    className="batch-select-all-btn"
                    onClick={handleDeselectAll}
                  >
                    {intl.formatMessage({ id: 'batchEdit.deselectAll' })}
                  </button>
                </>
              )}
            </div>
          )}

          {selectionMode && checkedIds.size > 0 && (
            <div className="search-collection-toolbar">
              <button type="button" className="bulk-add-btn" onClick={handleBulkAddToCollection}>
                {intl.formatMessage({ id: 'collections.bulkAdd' }, { count: checkedIds.size })}
              </button>
            </div>
          )}
        </header>

        <ErrorBoundary fallback={renderSearchResultsFallback}>
          <Profiler id="SearchResults" onRender={onRenderCallback}>
            <SearchResultsSection
              error={error}
              hasActiveFilters={hasActiveFilters}
              loading={loading}
              page={searchState.page}
              limit={searchState.limit}
              query={searchState.query}
              results={results}
              resultsRegionId={resultsRegionId}
              resultsRegionRef={resultsRegionRef}
              resultsSummaryId={resultsSummaryId}
              selectedBook={selectedBook}
              total={total}
              onOpenPdf={handleOpenPdf}
              onPageChange={setPage}
              onPdfClose={handleClosePdf}
              onSelectSimilarBook={handleSelectSimilarBook}
              selectionMode={selectionMode}
              checkedIds={checkedIds}
              onToggleSelect={handleToggleSelect}
              onSaveToCollection={handleSaveToCollection}
            />
          </Profiler>
        </ErrorBoundary>
      </main>

      <AddToCollectionModal
        open={addToCollectionOpen}
        onClose={handleAddToCollectionClose}
        documentIds={addToCollectionDocIds}
        onSuccess={handleAddToCollectionSuccess}
      />
    </div>
  );
}

export default SearchPage;
