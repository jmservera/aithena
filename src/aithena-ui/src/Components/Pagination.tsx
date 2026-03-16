import { memo, useMemo } from 'react';

interface PaginationProps {
  page: number;
  limit: number;
  total: number;
  onPageChange: (page: number) => void;
}

const Pagination = memo(function Pagination({ page, limit, total, onPageChange }: PaginationProps) {
  const totalPages = useMemo(() => Math.ceil(total / limit), [total, limit]);
  const pages = useMemo<(number | '…')[]>(() => {
    if (totalPages <= 1) {
      return [];
    }

    const nextPages: (number | '…')[] = [];
    if (totalPages <= 7) {
      for (let index = 1; index <= totalPages; index += 1) {
        nextPages.push(index);
      }
      return nextPages;
    }

    nextPages.push(1);
    if (page > 3) {
      nextPages.push('…');
    }
    for (
      let index = Math.max(2, page - 1);
      index <= Math.min(totalPages - 1, page + 1);
      index += 1
    ) {
      nextPages.push(index);
    }
    if (page < totalPages - 2) {
      nextPages.push('…');
    }
    nextPages.push(totalPages);

    return nextPages;
  }, [page, totalPages]);

  if (totalPages <= 1) return null;

  return (
    <nav className="pagination" aria-label="Search results pagination">
      <button
        className="pagination-btn"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        aria-label="Previous page"
      >
        ‹
      </button>
      {pages.map((paginationItem, index) =>
        paginationItem === '…' ? (
          <span key={`ellipsis-${index}`} className="pagination-ellipsis">
            …
          </span>
        ) : (
          <button
            key={paginationItem}
            className={`pagination-btn${page === paginationItem ? ' active' : ''}`}
            onClick={() => onPageChange(paginationItem)}
            aria-current={page === paginationItem ? 'page' : undefined}
          >
            {paginationItem}
          </button>
        )
      )}
      <button
        className="pagination-btn"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        aria-label="Next page"
      >
        ›
      </button>
    </nav>
  );
});

export default Pagination;
