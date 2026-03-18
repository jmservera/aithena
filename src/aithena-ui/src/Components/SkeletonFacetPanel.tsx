import './SkeletonFacetPanel.css';

function SkeletonFacetPanel() {
  return (
    <div className="facet-panel skeleton-facet-panel" aria-hidden="true">
      {Array.from({ length: 4 }, (_, groupIndex) => (
        <div key={`skeleton-group-${groupIndex}`} className="facet-group">
          <div className="skeleton skeleton--facet-title"></div>
          <ul className="facet-list">
            {Array.from({ length: 3 + (groupIndex % 2) }, (_, itemIndex) => (
              <li key={`skeleton-item-${itemIndex}`} className="facet-item">
                <div className="skeleton-facet-label">
                  <div className="skeleton skeleton--checkbox"></div>
                  <div className="skeleton skeleton--facet-value"></div>
                  <div className="skeleton skeleton--facet-count"></div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default SkeletonFacetPanel;
