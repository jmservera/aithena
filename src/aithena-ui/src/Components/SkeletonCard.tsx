import './SkeletonCard.css';

interface SkeletonCardProps {
  count?: number;
}

function SkeletonCard({ count = 1 }: SkeletonCardProps) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <li key={`skeleton-${index}`} className="search-results-item">
          <article className="book-card skeleton-card" aria-hidden="true">
            <div className="skeleton skeleton--title"></div>
            <div className="skeleton-meta">
              <div className="skeleton skeleton--meta"></div>
              <div className="skeleton skeleton--meta"></div>
              <div className="skeleton skeleton--meta"></div>
            </div>
            <div className="skeleton-highlights">
              <div className="skeleton skeleton--highlight"></div>
              <div className="skeleton skeleton--highlight"></div>
            </div>
            <div className="skeleton-footer">
              <div className="skeleton skeleton--filepath"></div>
              <div className="skeleton skeleton--button"></div>
            </div>
          </article>
        </li>
      ))}
    </>
  );
}

export default SkeletonCard;
