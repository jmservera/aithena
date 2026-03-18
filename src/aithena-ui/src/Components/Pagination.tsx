import { memo, useMemo } from 'react';
import { useIntl } from 'react-intl';

interface PaginationProps {
  page: number;
  limit: number;
  total: number;
  onPageChange: (page: number) => void;
  controlsId?: string;
}

const Pagination = memo(function Pagination({
  page,
  limit,
  total,
  onPageChange,
  controlsId,
}: PaginationProps) {
  const intl = useIntl();
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
    <nav className="pagination" aria-label={intl.formatMessage({ id: 'pagination.ariaLabel' })}>
      <button
        type="button"
        className="pagination-btn"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        aria-label={intl.formatMessage({ id: 'pagination.previousPage' })}
        aria-controls={controlsId}
      >
        ‹
      </button>
      {pages.map((paginationItem, index) =>
        paginationItem === '…' ? (
          <span key={`ellipsis-${index}`} className="pagination-ellipsis" aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={paginationItem}
            type="button"
            className={`pagination-btn${page === paginationItem ? ' active' : ''}`}
            onClick={() => onPageChange(paginationItem)}
            aria-current={page === paginationItem ? 'page' : undefined}
            aria-controls={controlsId}
          >
            {paginationItem}
          </button>
        )
      )}
      <button
        type="button"
        className="pagination-btn"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        aria-label={intl.formatMessage({ id: 'pagination.nextPage' })}
        aria-controls={controlsId}
      >
        ›
      </button>
    </nav>
  );
});

export default Pagination;
