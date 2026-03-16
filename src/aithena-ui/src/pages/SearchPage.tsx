import { useState, useCallback, FormEvent } from 'react';
import ErrorBoundary, { ErrorBoundaryFallbackProps } from '../Components/ErrorBoundary';
import { useSearch, BookResult, SearchMode } from '../hooks/search';
import { SearchFilters } from '../hooks/search';
import { getCachedSimilarBook } from '../hooks/similarBooks';
import FacetPanel from '../Components/FacetPanel';
import ActiveFilters from '../Components/ActiveFilters';
import BookCard from '../Components/BookCard';
import Pagination from '../Components/Pagination';
import PdfViewer from '../Components/PdfViewer';
import SimilarBooks from '../Components/SimilarBooks';

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
  selectedBook,
  total,
  onOpenPdf,
  onPageChange,
  onPdfClose,
  onSelectSimilarBook,
}: SearchResultsSectionProps) {
  const totalPages = Math.ceil(total / limit);

  return (
    <>
      <section className="search-results">
        {error && (
          <div className="search-error" role="alert">
            ⚠️ {error}
          </div>
        )}

        {!loading && !error && query && results.length === 0 && (
          <div className="search-empty">
            No results found for &ldquo;{query}&rdquo;
            {hasActiveFilters && ' with the selected filters'}.
          </div>
        )}

        {!query && !loading && (
          <div className="search-empty">Enter a search term above to find books.</div>
        )}

        {results.map((book) => (
          <BookCard
            key={book.id}
            book={book}
            onOpenPdf={onOpenPdf}
            isSelected={selectedBook?.id === book.id}
          />
        ))}
      </section>

      {selectedBook && (
        <SimilarBooks documentId={selectedBook.id} onSelectBook={onSelectSimilarBook} />
      )}

      {total > 0 && (
        <footer className="search-footer">
          <Pagination page={page} limit={limit} total={total} onPageChange={onPageChange} />
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
  const [inputValue, setInputValue] = useState('');
  const [selectedBook, setSelectedBook] = useState<BookResult | null>(null);
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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setQuery(inputValue.trim());
  }

  function handleRemoveFilter(key: keyof SearchFilters) {
    setFilter(key, undefined);
  }

  const hasActiveFilters = Object.values(searchState.filters).some(
    (v) => v !== undefined && v !== ''
  );

  const handleOpenPdf = useCallback((book: BookResult) => {
    setSelectedBook(book);
  }, []);

  const handleSelectSimilarBook = useCallback(
    (bookId: string) => {
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
          <form className="search-form" onSubmit={handleSubmit}>
            <input
              className="search-input"
              type="search"
              value={inputValue}
              placeholder="Search books by title, author, or content…"
              onChange={(e) => setInputValue(e.target.value)}
              aria-label="Search query"
            />
            <button className="search-btn" type="submit" disabled={loading}>
              {loading ? '…' : 'Search'}
            </button>
          </form>

          <div className="mode-selector" role="group" aria-label="Search mode">
            {MODE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`mode-btn${searchState.mode === opt.value ? ' mode-btn--active' : ''}`}
                onClick={() => setMode(opt.value)}
                title={opt.title}
                aria-pressed={searchState.mode === opt.value}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {searchState.query && (
            <div className="search-controls">
              <span className="search-result-count">
                {loading ? (
                  'Searching…'
                ) : (
                  <>
                    {total.toLocaleString()} result{total !== 1 ? 's' : ''} for &ldquo;
                    {searchState.query}&rdquo;
                    <span
                      className={`mode-badge ${MODE_BADGE_CLASS[searchState.mode]}`}
                      title={`Search mode: ${searchState.mode}`}
                    >
                      {searchState.mode}
                    </span>
                  </>
                )}
              </span>
              <div className="search-sort-limit">
                <label htmlFor="sort-select" className="control-label">
                  Sort:
                </label>
                <select
                  id="sort-select"
                  className="sort-select"
                  value={searchState.sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  {SORT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
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
                  onChange={(e) => setLimit(Number(e.target.value))}
                >
                  {[10, 20, 50].map((n) => (
                    <option key={n} value={n}>
                      {n}
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
          <SearchResultsSection
            error={error}
            hasActiveFilters={hasActiveFilters}
            loading={loading}
            page={searchState.page}
            limit={searchState.limit}
            query={searchState.query}
            results={results}
            selectedBook={selectedBook}
            total={total}
            onOpenPdf={handleOpenPdf}
            onPageChange={setPage}
            onPdfClose={() => setSelectedBook(null)}
            onSelectSimilarBook={handleSelectSimilarBook}
          />
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default SearchPage;
