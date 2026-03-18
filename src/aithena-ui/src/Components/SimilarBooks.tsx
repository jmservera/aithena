import { useIntl } from 'react-intl';

import { SimilarBook, useSimilarBooks } from '../hooks/similarBooks';

interface SimilarBooksProps {
  documentId: string;
  onSelectBook: (bookId: string) => void;
}

function SimilarBookCard({
  book,
  onSelectBook,
}: {
  book: SimilarBook;
  onSelectBook: (bookId: string) => void;
}) {
  const intl = useIntl();

  return (
    <button
      type="button"
      className="similar-book-card"
      onClick={() => onSelectBook(book.id)}
      aria-label={intl.formatMessage({ id: 'book.openSimilarBook' }, { title: book.title })}
    >
      <div className="similar-book-card__header">
        <h3 className="similar-book-card__title">{book.title}</h3>
        <span className="similarity-score">
          {intl.formatMessage(
            { id: 'book.similarityScore' },
            { score: Math.round(book.score * 100) }
          )}
        </span>
      </div>
      <p className="similar-book-card__author">
        {book.author || intl.formatMessage({ id: 'book.unknownAuthor' })}
      </p>
      <div className="similar-book-card__meta">
        {book.year && <span>{book.year}</span>}
        {book.category && <span>{book.category}</span>}
      </div>
    </button>
  );
}

function SimilarBooks({ documentId, onSelectBook }: SimilarBooksProps) {
  const intl = useIntl();
  const { books, loading, error } = useSimilarBooks(documentId);

  return (
    <section className="similar-books-panel" aria-labelledby="similar-books-title">
      <div className="similar-books-header">
        <h2 id="similar-books-title" className="similar-books-title">
          {intl.formatMessage({ id: 'book.similarBooks' })}
        </h2>
        <p className="similar-books-subtitle">
          {intl.formatMessage({ id: 'book.similarBooksSubtitle' })}
        </p>
      </div>

      {loading ? (
        <>
          <div className="similar-books-loading" role="status" aria-live="polite">
            {intl.formatMessage({ id: 'book.loadingSimilarBooks' })}
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
          {intl.formatMessage({ id: 'book.similarBooksError' })}
        </p>
      ) : books.length === 0 ? (
        <p className="similar-books-message">{intl.formatMessage({ id: 'book.noSimilarBooks' })}</p>
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
