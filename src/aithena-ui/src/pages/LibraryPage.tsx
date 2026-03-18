import { useCallback, useId, useRef, useState, useEffect } from 'react';
import { useLibrary } from '../hooks/library';
import { BookResult, SearchFilters } from '../hooks/search';
import FacetPanel from '../Components/FacetPanel';
import ActiveFilters from '../Components/ActiveFilters';
import BookCard from '../Components/BookCard';
import Pagination from '../Components/Pagination';
import PdfViewer from '../Components/PdfViewer';
import SimilarBooks from '../Components/SimilarBooks';
import { getCachedSimilarBook } from '../hooks/similarBooks';

const SORT_OPTIONS = [
  { value: 'title_s asc', label: 'Title (A–Z)' },
  { value: 'title_s desc', label: 'Title (Z–A)' },
  { value: 'author_s asc', label: 'Author (A–Z)' },
  { value: 'author_s desc', label: 'Author (Z–A)' },
  { value: 'year_i desc', label: 'Year (newest)' },
  { value: 'year_i asc', label: 'Year (oldest)' },
];

function LibraryPage() {
  const {
    libraryState,
    results,
    facets,
    total,
    loading,
    error,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
  } = useLibrary();

  const [selectedBook, setSelectedBook] = useState<BookResult | null>(null);
  const resultsRegionRef = useRef<HTMLElement>(null);
  const lastLoadingStateRef = useRef(false);
  const lastPdfTriggerRef = useRef<HTMLElement | null>(null);
  const resultsRegionId = useId();
  const resultsSummaryId = useId();

  useEffect(() => {
    if (lastLoadingStateRef.current && !loading && results.length > 0) {
      resultsRegionRef.current?.focus();
    }
    lastLoadingStateRef.current = loading;
  }, [loading, results.length]);

  function handleRemoveFilter(key: keyof SearchFilters) {
    setFilter(key, undefined);
  }

  const hasActiveFilters = Object.values(libraryState.filters).some(
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

  const totalPages = Math.ceil(total / libraryState.limit);
  const resultsHeadingId = `${resultsRegionId}-heading`;

  return (
    <div className="search-layout">
      <aside className="sidebar">
        <FacetPanel facets={facets} filters={libraryState.filters} onFilterChange={setFilter} />
      </aside>

      <main className="search-main">
        <header className="search-header">
          <h1 className="page-title">📖 Library</h1>

          <div className="search-controls">
            <p
              id={resultsSummaryId}
              className="search-result-count"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              {loading ? (
                'Loading…'
              ) : (
                <>
                  {total.toLocaleString()} book{total !== 1 ? 's' : ''} in collection
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
                value={libraryState.sort}
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
                value={libraryState.limit}
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

          {hasActiveFilters && (
            <ActiveFilters
              filters={libraryState.filters}
              onRemove={handleRemoveFilter}
              onClearAll={clearFilters}
            />
          )}
        </header>

        <section
          id={resultsRegionId}
          ref={resultsRegionRef}
          className="search-results"
          role="region"
          aria-labelledby={resultsHeadingId}
          aria-describedby={resultsSummaryId}
          aria-busy={loading}
          tabIndex={-1}
        >
          <h2 id={resultsHeadingId} className="visually-hidden">
            Library books
          </h2>

          {error && (
            <div className="search-error" role="alert">
              ⚠️ {error}
            </div>
          )}

          {!loading && !error && results.length === 0 && (
            <div className="search-empty">
              No books found
              {hasActiveFilters && ' with the selected filters'}.
            </div>
          )}

          {results.length > 0 && (
            <ul className="search-results-list">
              {results.map((book) => (
                <li key={book.id} className="search-results-item">
                  <BookCard
                    book={book}
                    onOpenPdf={handleOpenPdf}
                    isSelected={selectedBook?.id === book.id}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        {selectedBook && (
          <SimilarBooks documentId={selectedBook.id} onSelectBook={handleSelectSimilarBook} />
        )}

        {total > 0 && (
          <footer className="search-footer">
            <Pagination
              page={libraryState.page}
              limit={libraryState.limit}
              total={total}
              onPageChange={setPage}
              controlsId={resultsRegionId}
            />
            <p className="pagination-info">
              Page {libraryState.page} of {totalPages}
            </p>
          </footer>
        )}

        {selectedBook && <PdfViewer result={selectedBook} onClose={handleClosePdf} />}
      </main>
    </div>
  );
}

export default LibraryPage;
