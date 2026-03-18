import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import FacetPanel from '../Components/FacetPanel';
import { IntlWrapper } from './test-intl-wrapper';
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
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    expect(screen.getByText('Author')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Year')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Programming')).toBeInTheDocument();
  });

  it('does not render a facet group when it has no values', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    // "language" facet has an empty array and should not render
    expect(screen.queryByText('Language')).not.toBeInTheDocument();
  });

  it('calls onFilterChange with the selected value when a facet checkbox is clicked', async () => {
    const onFilterChange = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    await user.click(checkbox);

    expect(onFilterChange).toHaveBeenCalledWith('author', 'Jane Doe');
  });

  it('marks a checkbox as checked when the corresponding filter is active', () => {
    const onFilterChange = vi.fn();
    const filters: SearchFilters = { author: 'Jane Doe' };
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={filters} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    expect(checkbox).toBeChecked();
  });

  it('calls onFilterChange with undefined to deselect when an active facet is clicked', async () => {
    const onFilterChange = vi.fn();
    const user = userEvent.setup();
    const filters: SearchFilters = { author: 'Jane Doe' };
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={filters} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    const checkbox = screen.getByRole('checkbox', { name: /jane doe/i });
    await user.click(checkbox);

    expect(onFilterChange).toHaveBeenCalledWith('author', undefined);
  });

  it('renders facet counts', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    expect(screen.getByText('(3)')).toBeInTheDocument();
    expect(screen.getByText('(4)')).toBeInTheDocument();
  });

  it('shows informational message when mode is semantic', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} mode="semantic" />
      </IntlWrapper>
    );

    const msg = screen.getByRole('note');
    expect(msg).toBeInTheDocument();
    expect(msg).toHaveTextContent('Facets are only available in keyword mode');
  });

  it('hides facet groups when mode is semantic', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} mode="semantic" />
      </IntlWrapper>
    );

    expect(screen.queryByText('Author')).not.toBeInTheDocument();
    expect(screen.queryByText('Category')).not.toBeInTheDocument();
  });

  it('does not show the semantic message when mode is keyword', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} mode="keyword" />
      </IntlWrapper>
    );

    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    expect(screen.getByText('Author')).toBeInTheDocument();
  });

  it('does not show the semantic message when mode is hybrid', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} mode="hybrid" />
      </IntlWrapper>
    );

    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    expect(screen.getByText('Author')).toBeInTheDocument();
  });

  it('does not show the semantic message when mode is undefined', () => {
    const onFilterChange = vi.fn();
    render(
      <IntlWrapper>
        <FacetPanel facets={facets} filters={{}} onFilterChange={onFilterChange} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });
});
