import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import FacetPanel from '../Components/FacetPanel';
import { FacetGroups, SearchFilters } from '../hooks/search';

const facets: FacetGroups = {
  author: [
    { value: 'Jane Doe', count: 3 },
    { value: 'John Smith', count: 1 },
  ],
  category: [{ value: 'Programming', count: 4 }],
  language: [],
  year: [
    { value: '2020', count: 2 },
    { value: '2021', count: 1 },
  ],
};

describe('FacetPanel', () => {
  it('renders facet groups with values', () => {
    const onFilterChange = vi.fn();
    render(<FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />);

    expect(screen.getByText('Author')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Year')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Programming')).toBeInTheDocument();
  });

  it('does not render a facet group when it has no values', () => {
    const onFilterChange = vi.fn();
    render(<FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />);

    // "language" facet has an empty array and should not render
    expect(screen.queryByText('Language')).not.toBeInTheDocument();
  });

  it('calls onFilterChange with the selected value when a facet checkbox is clicked', async () => {
    const onFilterChange = vi.fn();
    const user = userEvent.setup();
    render(<FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />);

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    await user.click(checkbox);

    expect(onFilterChange).toHaveBeenCalledWith('author', 'Jane Doe');
  });

  it('marks a checkbox as checked when the corresponding filter is active', () => {
    const onFilterChange = vi.fn();
    const filters: SearchFilters = { author: 'Jane Doe' };
    render(<FacetPanel facets={facets} filters={filters} onFilterChange={onFilterChange} />);

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    expect(checkbox).toBeChecked();
  });

  it('calls onFilterChange with undefined to deselect when an active facet is clicked', async () => {
    const onFilterChange = vi.fn();
    const user = userEvent.setup();
    const filters: SearchFilters = { author: 'Jane Doe' };
    render(<FacetPanel facets={facets} filters={filters} onFilterChange={onFilterChange} />);

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    await user.click(checkbox);

    expect(onFilterChange).toHaveBeenCalledWith('author', undefined);
  });

  it('renders facet counts', () => {
    const onFilterChange = vi.fn();
    render(<FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />);

    expect(screen.getByText('(3)')).toBeInTheDocument();
    expect(screen.getByText('(4)')).toBeInTheDocument();
  });
});
