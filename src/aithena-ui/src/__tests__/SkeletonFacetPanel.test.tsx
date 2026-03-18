import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import SkeletonFacetPanel from '../Components/SkeletonFacetPanel';

describe('SkeletonFacetPanel', () => {
  it('renders skeleton facet panel', () => {
    const { container } = render(<SkeletonFacetPanel />);
    const panel = container.querySelector('.skeleton-facet-panel');
    expect(panel).toBeInTheDocument();
  });

  it('hides skeleton from screen readers', () => {
    const { container } = render(<SkeletonFacetPanel />);
    const panel = container.querySelector('.skeleton-facet-panel');
    expect(panel).toHaveAttribute('aria-hidden', 'true');
  });

  it('renders multiple facet groups', () => {
    const { container } = render(<SkeletonFacetPanel />);
    const groups = container.querySelectorAll('.facet-group');
    expect(groups.length).toBeGreaterThan(0);
  });

  it('renders facet items with checkboxes, values, and counts', () => {
    const { container } = render(<SkeletonFacetPanel />);

    expect(container.querySelector('.skeleton--checkbox')).toBeInTheDocument();
    expect(container.querySelector('.skeleton--facet-value')).toBeInTheDocument();
    expect(container.querySelector('.skeleton--facet-count')).toBeInTheDocument();
  });

  it('applies shimmer animation class to elements', () => {
    const { container } = render(<SkeletonFacetPanel />);
    const shimmerElements = container.querySelectorAll('.skeleton--facet-title');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });

  it('matches FacetPanel structure', () => {
    const { container } = render(<SkeletonFacetPanel />);

    expect(container.querySelector('.facet-panel')).toBeInTheDocument();
    expect(container.querySelector('.facet-group')).toBeInTheDocument();
    expect(container.querySelector('.facet-list')).toBeInTheDocument();
    expect(container.querySelector('.facet-item')).toBeInTheDocument();
  });
});
