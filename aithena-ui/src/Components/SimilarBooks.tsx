import { SimilarBook, useSimilarBooks } from '../hooks/similarBooks';

interface SimilarBooksProps {
  documentId: string;
  onSelectBook: (bookId: string) => void;
}

function formatSimilarityScore(score: number): string {
  return `${Math.round(score * 100)}% match`;
}

function SimilarBookCard({
  book,
  onSelectBook,
}: {
  book: SimilarBook;
  onSelectBook: (bookId: string) => void;
}) {
  return (
    <button
      type="button"
      className="similar-book-card"
      onClick={() => onSelectBook(book.id)}
      aria-label={`Open similar book ${book.title}`}
    >
      <div className="similar-book-card__header">
        <h3 className="similar-book-card__title">{book.title}</h3>
        <span className="similarity-score">{formatSimilarityScore(book.score)}</span>
      </div>
      <p className="similar-book-card__author">{book.author || 'Unknown author'}</p>
      <div className="similar-book-card__meta">
        {book.year && <span>{book.year}</span>}
        {book.category && <span>{book.category}</span>}
      </div>
    </button>
  );
}

function SimilarBooks({ documentId, onSelectBook }: SimilarBooksProps) {
  const { books, loading, error } = useSimilarBooks(documentId);

  return (
    <section className="similar-books-panel" aria-labelledby="similar-books-title">
      <div className="similar-books-header">
        <h2 id="similar-books-title" className="similar-books-title">
          Similar Books
        </h2>
        <p className="similar-books-subtitle">
          Readers also looked at these semantically related titles.
        </p>
      </div>

      {loading ? (
        <>
          <div className="similar-books-loading" role="status" aria-live="polite">
            Loading similar books…
          </div>
          <div className="similar-books-list" aria-hidden="true">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="similar-book-card similar-book-card--loading">
                <div className="similar-book-card__skeleton similar-book-card__skeleton--title" />
                <div className="similar-book-card__skeleton similar-book-card__skeleton--text" />
                <div className="similar-book-card__skeleton similar-book-card__skeleton--text" />
              </div>
            ))}
          </div>
        </>
      ) : error ? (
        <p className="similar-books-message similar-books-message--error" role="alert">
          We couldn’t load similar books right now. Try another title in a moment.
        </p>
      ) : books.length === 0 ? (
        <p className="similar-books-message">No similar books found</p>
      ) : (
        <div className="similar-books-list">
          {books.map((book) => (
            <SimilarBookCard key={book.id} book={book} onSelectBook={onSelectBook} />
          ))}
        </div>
      )}
    </section>
  );
}

export default SimilarBooks;
