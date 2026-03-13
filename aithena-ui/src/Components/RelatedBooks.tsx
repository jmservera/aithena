import { SimilarBook } from "../hooks/similarBooks";

interface RelatedBooksProps {
  state: "idle" | "loading" | "success" | "error";
  error: string | null;
  similar: SimilarBook[];
  onSelect: (book: SimilarBook) => void;
}

function RelatedBooks({ state, error, similar, onSelect }: RelatedBooksProps) {
  return (
    <aside className="related-books-panel" aria-label="Related books">
      <h2 className="related-books-title">Related Books</h2>

      {state === "loading" && (
        <div className="related-books-loading" role="status">
          <span className="spinner" aria-hidden="true" />
          Finding related books…
        </div>
      )}

      {state === "error" && (
        <p className="related-books-error" role="alert">
          {error ?? "Could not load related books."}
        </p>
      )}

      {state === "success" && similar.length === 0 && (
        <p className="related-books-empty">No related books found.</p>
      )}

      {state === "success" && similar.length > 0 && (
        <ul className="related-books-list" aria-label="Similar books">
          {similar.map((book) => (
            <li key={book.id} className="related-books-item">
              <button
                className="related-book-card"
                onClick={() => onSelect(book)}
                title={`Open ${book.title}`}
              >
                <span className="related-book-title">
                  {book.title || "Untitled"}
                </span>
                <div className="related-book-meta">
                  {book.author && (
                    <span className="book-author">{book.author}</span>
                  )}
                  {book.year && (
                    <span className="book-year">{book.year}</span>
                  )}
                  {book.category && (
                    <span className="book-category">{book.category}</span>
                  )}
                </div>
                <span className="related-book-score">
                  {Math.round(book.score * 100)}% match
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

export default RelatedBooks;
