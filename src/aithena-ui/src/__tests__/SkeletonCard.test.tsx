import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import SkeletonCard from '../Components/SkeletonCard';

describe('SkeletonCard', () => {
  it('renders a single skeleton card by default', () => {
    const { container } = render(<SkeletonCard />);
    const skeletonCards = container.querySelectorAll('.skeleton-card');
    expect(skeletonCards).toHaveLength(1);
  });

  it('renders multiple skeleton cards based on count prop', () => {
    const { container } = render(<SkeletonCard count={5} />);
    const skeletonCards = container.querySelectorAll('.skeleton-card');
    expect(skeletonCards).toHaveLength(5);
  });

  it('hides skeleton from screen readers', () => {
    const { container } = render(<SkeletonCard />);
    const skeletonCard = container.querySelector('.skeleton-card');
    expect(skeletonCard).toHaveAttribute('aria-hidden', 'true');
  });

  it('renders all skeleton elements (title, meta, highlights, footer)', () => {
    const { container } = render(<SkeletonCard />);

    expect(container.querySelector('.skeleton--title')).toBeInTheDocument();
    expect(container.querySelector('.skeleton-meta')).toBeInTheDocument();
    expect(container.querySelector('.skeleton-highlights')).toBeInTheDocument();
    expect(container.querySelector('.skeleton-footer')).toBeInTheDocument();
  });

  it('renders with list item structure matching BookCard', () => {
    const { container } = render(<SkeletonCard count={2} />);
    const listItems = container.querySelectorAll('.search-results-item');
    expect(listItems).toHaveLength(2);
  });

  it('applies shimmer animation class', () => {
    const { container } = render(<SkeletonCard />);
    const shimmerElements = container.querySelectorAll('.skeleton');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });
});
