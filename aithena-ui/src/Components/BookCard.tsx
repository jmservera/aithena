import { BookResult } from "../hooks/search";

interface BookCardProps {
  book: BookResult;
}

function BookCard({ book }: BookCardProps) {
  return (
    <article className="book-card">
      <h2 className="book-title">{book.title}</h2>
      <div className="book-meta">
        {book.author && (
          <span className="book-meta-item">
            <span className="book-meta-label">Author:</span> {book.author}
          </span>
        )}
        {book.year && (
          <span className="book-meta-item">
            <span className="book-meta-label">Year:</span> {book.year}
          </span>
        )}
        {book.category && (
          <span className="book-meta-item">
            <span className="book-meta-label">Category:</span> {book.category}
          </span>
        )}
        {book.language && (
          <span className="book-meta-item">
            <span className="book-meta-label">Language:</span> {book.language}
          </span>
        )}
        {book.page_count !== undefined && (
          <span className="book-meta-item">
            <span className="book-meta-label">Pages:</span> {book.page_count}
          </span>
        )}
      </div>
      {book.highlights && book.highlights.length > 0 && (
        <div className="book-highlights">
          {book.highlights.map((snippet, i) => (
            <p
              key={i}
              className="book-highlight-snippet"
              dangerouslySetInnerHTML={{ __html: `…${snippet}…` }}
            />
          ))}
        </div>
      )}
      {book.file_path && (
        <p className="book-filepath">{book.file_path}</p>
      )}
    </article>
  );
}

export default BookCard;
