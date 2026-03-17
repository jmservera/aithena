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
import ErrorBoundary, { ErrorBoundaryFallbackProps } from '../Components/ErrorBoundary';
import FacetPanel from '../Components/FacetPanel';
import ActiveFilters from '../Components/ActiveFilters';
import BookCard from '../Components/BookCard';
import Pagination from '../Components/Pagination';
import PdfViewer from '../Components/PdfViewer';
import SimilarBooks from '../Components/SimilarBooks';
import { SearchFilters } from '../hooks/search';
import { getCachedSimilarBook } from '../hooks/similarBooks';
import { useSearch, BookResult, SearchMode } from '../hooks/search';
import { onRenderCallback } from '../utils/profiler';

const SORT_OPTIONS = [
  { value: 'score desc', label: 'Relevance' },
  { value: 'year_i desc', label: 'Year (newest)' },
  { value: 'year_i asc', label: 'Year (oldest)' },
  { value: 'title_s asc', label: 'Title (A–Z)' },
  { value: 'author_s asc', label: 'Author (A–Z)' },
];

const MODE_OPTIONS: { value: SearchMode; label: string; title: string }[] = [
  { value: 'keyword', label: 'Keyword', title: 'Traditional keyword search' },
  { value: 'semantic', label: 'Semantic', title: 'Vector-based semantic search' },
  { value: 'hybrid', label: 'Hybrid', title: 'Combined keyword + semantic search' },
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
  resultsRegionRef: RefObject<HTMLElement>;
  resultsSummaryId: string;
  selectedBook: BookResult | null;
  total: number;
  onOpenPdf: (book: BookResult) => void;
  onPageChange: (page: number) => void;
  onPdfClose: () => void;
  onSelectSimilarBook: (bookId: string) => void;
}

function renderSearchResultsFallback({ reset, reload }: ErrorBoundaryFallbackProps) {
  return (
    <section className="error-boundary error-boundary--section" role="alert" aria-live="assertive">
      <h2 className="error-boundary__title error-boundary__title--section">
        Search results are temporarily unavailable.
      </h2>
      <p className="error-boundary__message">
        Your current search settings are still here. Try loading the results again or reload the
        app.
      </p>
      <div className="error-boundary__actions">
        <button type="button" className="error-boundary__button" onClick={reset}>
          Try again
        </button>
        <button
          type="button"
          className="error-boundary__button error-boundary__button--secondary"
          onClick={reload}
        >
          Reload app
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
}: SearchResultsSectionProps) {
  const totalPages = Math.ceil(total / limit);
  const resultsHeadingId = `${resultsRegionId}-heading`;

  return (
    <>
      <section
        id={resultsRegionId}
        ref={resultsRegionRef}
        className="search-results"
        role="region"
        aria-labelledby={resultsHeadingId}
        aria-describedby={query ? resultsSummaryId : undefined}
        aria-busy={loading}
        tabIndex={-1}
      >
        <h2 id={resultsHeadingId} className="visually-hidden">
          Search results
        </h2>

        {error && (
          <div className="search-error" role="alert">
            ⚠️ {error}
          </div>
        )}

        {!loading && !error && !query && (
          <div className="search-empty">Enter a search term above to find books.</div>
        )}

        {!loading && !error && query && results.length === 0 && (
          <div className="search-empty">
            No results found for &ldquo;{query}&rdquo;
            {hasActiveFilters && ' with the selected filters'}.
          </div>
        )}

        {results.length > 0 && (
          <ul className="search-results-list">
            {results.map((book) => (
              <li key={book.id} className="search-results-item">
                <BookCard
                  book={book}
                  onOpenPdf={onOpenPdf}
                  isSelected={selectedBook?.id === book.id}
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
            Page {page} of {totalPages}
          </p>
        </footer>
      )}

      {selectedBook && <PdfViewer result={selectedBook} onClose={onPdfClose} />}
    </>
  );
}

function SearchPage() {
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

  useEffect(() => {
    setInputValue(searchState.query);
  }, [searchState.query]);

  const [selectedBook, setSelectedBook] = useState<BookResult | null>(null);
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

  return (
    <div className="search-layout">
      <aside className="sidebar">
        <FacetPanel
          facets={facets}
          filters={searchState.filters}
          onFilterChange={setFilter}
          mode={searchState.mode}
        />
      </aside>

      <main className="search-main">
        <header className="search-header">
          <form
            className="search-form"
            role="search"
            aria-label="Search the library"
            onSubmit={handleSubmit}
          >
            <label className="visually-hidden" htmlFor={searchInputId}>
              Search books by title, author, or content
            </label>
            <input
              id={searchInputId}
              className="search-input"
              type="search"
              value={inputValue}
              placeholder="Search books by title, author, or content…"
              onChange={(event) => setInputValue(event.target.value)}
              aria-label="Search query"
            />
            <button className="search-btn" type="submit" disabled={loading}>
              {loading ? '…' : 'Search'}
            </button>
          </form>

          <div className="mode-selector" role="group" aria-label="Search mode">
            {MODE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`mode-btn${searchState.mode === option.value ? ' mode-btn--active' : ''}`}
                onClick={() => setMode(option.value)}
                title={option.title}
                aria-pressed={searchState.mode === option.value}
              >
                {option.label}
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
                  'Searching…'
                ) : (
                  <>
                    {total.toLocaleString()} result{total !== 1 ? 's' : ''} for &ldquo;
                    {searchState.query}&rdquo;
                    <span
                      className={`mode-badge ${MODE_BADGE_CLASS[searchState.mode]}`}
                      title={`Search mode: ${searchState.mode}`}
                      aria-label={`Search mode: ${searchState.mode}`}
                    >
                      {searchState.mode}
                    </span>
                  </>
                )}
              </p>
              <div className="search-sort-limit">
                <label htmlFor="sort-select" className="control-label">
                  Sort:
                </label>
                <select
                  id="sort-select"
                  className="sort-select"
                  value={searchState.sort}
                  onChange={(event) => setSort(event.target.value)}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>

                <label htmlFor="limit-select" className="control-label">
                  Per page:
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
            />
          </Profiler>
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default SearchPage;
