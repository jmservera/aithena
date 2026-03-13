import "./App.css";
import { useState, FormEvent } from "react";
import { useSearch } from "./hooks/search";
import { SearchFilters } from "./hooks/search";
import FacetPanel from "./Components/FacetPanel";
import ActiveFilters from "./Components/ActiveFilters";
import BookCard from "./Components/BookCard";
import Pagination from "./Components/Pagination";

const SORT_OPTIONS = [
  { value: "score desc", label: "Relevance" },
  { value: "year_i desc", label: "Year (newest)" },
  { value: "year_i asc", label: "Year (oldest)" },
  { value: "title_s asc", label: "Title (A–Z)" },
  { value: "author_s asc", label: "Author (A–Z)" },
];

function App() {
  const [inputValue, setInputValue] = useState("");
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
  } = useSearch();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setQuery(inputValue.trim());
  }

  function handleRemoveFilter(key: keyof SearchFilters) {
    setFilter(key, undefined);
  }

  const hasActiveFilters = Object.values(searchState.filters).some(
    (v) => v !== undefined && v !== ""
  );

  const totalPages = Math.ceil(total / searchState.limit);

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
              {loading ? "…" : "Search"}
            </button>
          </form>

          {searchState.query && (
            <div className="search-controls">
              <span className="search-result-count">
                {loading
                  ? "Searching…"
                  : `${total.toLocaleString()} result${total !== 1 ? "s" : ""} for "${searchState.query}"`}
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
            <BookCard key={book.id} book={book} />
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
    </div>
  );
}

export default App;
