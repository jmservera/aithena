import "./App.css";
import BookResultCard from "./Components/BookResult";
import { useSearch } from "./hooks/search";
import { useState, FormEvent } from "react";

function App() {
  const [input, setInput] = useState("");
  const { results, total, state, error, lastQuery, search } = useSearch();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    search(input);
  }

  return (
    <div className="App">
      <header className="search-header">
        <h1 className="search-title">📚 Aithena</h1>
        <p className="search-subtitle">Book Library Search</p>
        <form className="search-form" onSubmit={handleSubmit}>
          <input
            className="search-input"
            type="search"
            value={input}
            placeholder="Search for books by title, author, or content…"
            onChange={(e) => setInput(e.target.value)}
            disabled={state === "loading"}
            aria-label="Search query"
          />
          <button
            className="search-button"
            type="submit"
            disabled={state === "loading" || !input.trim()}
            aria-label="Search"
          >
            {state === "loading" ? "Searching…" : "Search"}
          </button>
        </form>
      </header>

      <main className="search-results">
        {state === "loading" && (
          <div className="state-message loading-state" role="status">
            <span className="spinner" aria-hidden="true" />
            Searching…
          </div>
        )}

        {state === "error" && (
          <div className="state-message error-state" role="alert">
            <strong>Search failed:</strong> {error}
          </div>
        )}

        {state === "success" && results.length === 0 && (
          <div className="state-message empty-state" role="status">
            No results found for <em>"{lastQuery}"</em>. Try a different query.
          </div>
        )}

        {state === "success" && results.length > 0 && (
          <>
            <p className="results-summary">
              {total} result{total !== 1 ? "s" : ""} for{" "}
              <em>"{lastQuery}"</em>
            </p>
            <ul className="results-list" aria-label="Search results">
              {results.map((result) => (
                <li key={result.id} className="results-list-item">
                  <BookResultCard result={result} />
                </li>
              ))}
            </ul>
          </>
        )}

        {state === "idle" && (
          <div className="state-message idle-state">
            Enter a search query to find books in the library.
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
