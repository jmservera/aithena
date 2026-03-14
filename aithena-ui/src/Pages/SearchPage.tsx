import { useState } from "react";
import ActiveFilters from "../Components/ActiveFilters";
import AdvancedSearchBuilder, {
  SearchSubmission,
} from "../Components/AdvancedSearch/AdvancedSearchBuilder";
import BookCard from "../Components/BookCard";
import FacetPanel from "../Components/FacetPanel";
import Pagination from "../Components/Pagination";
import PdfViewer from "../Components/PdfViewer";
import { BookResult, SearchFilters, useSearch } from "../hooks/search";

const SORT_OPTIONS = [
  { value: "score desc", label: "Relevance" },
  { value: "year_i desc", label: "Year (newest)" },
  { value: "year_i asc", label: "Year (oldest)" },
  { value: "title_s asc", label: "Title (A–Z)" },
  { value: "author_s asc", label: "Author (A–Z)" },
];

function SearchPage() {
  const [selectedBook, setSelectedBook] = useState<BookResult | null>(null);
  const {
    searchState,
    results,
    facets,
    total,
    loading,
    error,
    submitSearch,
    setFilter,
    clearFilters,
    setPage,
    setSort,
    setLimit,
  } = useSearch();

  function handleSearch({ mode, query }: SearchSubmission) {
    submitSearch(query, mode);
  }

  function handleRemoveFilter(key: keyof SearchFilters) {
    setFilter(key, undefined);
  }

  const hasActiveFilters = Object.values(searchState.filters).some(
    (value) => value !== undefined && value !== ""
  );

  const totalPages = Math.ceil(total / searchState.limit);
  const languageOptions = (facets.language ?? []).map(({ value }) => String(value));

  return (
    <div className="App">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="sidebar-title">📚 Aithena</h1>
          <p className="sidebar-subtitle">Book Library Search</p>
        </div>
        <FacetPanel
          facets={facets}
          filters={searchState.filters}
          onFilterChange={setFilter}
        />
      </aside>

      <main className="search-main">
        <header className="search-header">
          <AdvancedSearchBuilder
            languages={languageOptions}
            loading={loading}
            onSearch={handleSearch}
          />

          {searchState.query && (
            <div className="search-controls">
              <span className="search-result-count">
                {loading
                  ? "Searching…"
                  : `${total.toLocaleString()} result${total !== 1 ? "s" : ""} for "${searchState.query}"`}
              </span>
              <div className="search-sort-limit">
                {searchState.mode !== "keyword" && (
                  <span className="search-mode-badge badge text-bg-info text-dark text-uppercase">
                    {searchState.mode}
                  </span>
                )}
                <label htmlFor="sort-select" className="control-label">
                  Sort:
                </label>
                <select
                  id="sort-select"
                  className="sort-select form-select"
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
                  className="sort-select form-select"
                  value={searchState.limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                >
                  {[10, 20, 50].map((pageSize) => (
                    <option key={pageSize} value={pageSize}>
                      {pageSize}
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

        <section className="search-results">
          {error && (
            <div className="search-error" role="alert">
              ⚠️ {error}
            </div>
          )}

          {!loading && !error && searchState.query && results.length === 0 && (
            <div className="search-empty">
              No results found for "{searchState.query}"
              {hasActiveFilters && " with the selected filters"}.
            </div>
          )}

          {!searchState.query && !loading && (
            <div className="search-empty">
              Enter a search term above to find books.
            </div>
          )}

          {results.map((book) => (
            <BookCard
              key={book.id}
              book={book}
              onOpenPdf={setSelectedBook}
              isSelected={selectedBook?.id === book.id}
            />
          ))}
        </section>

        {total > 0 && (
          <footer className="search-footer">
            <Pagination
              page={searchState.page}
              limit={searchState.limit}
              total={total}
              onPageChange={setPage}
            />
            <p className="pagination-info">
              Page {searchState.page} of {totalPages}
            </p>
          </footer>
        )}
      </main>

      {selectedBook && (
        <PdfViewer result={selectedBook} onClose={() => setSelectedBook(null)} />
      )}
    </div>
  );
}

export default SearchPage;
