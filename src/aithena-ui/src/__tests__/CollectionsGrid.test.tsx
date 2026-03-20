import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import CollectionsGrid from '../Components/CollectionsGrid';
import { IntlWrapper } from './test-intl-wrapper';
import { type Collection } from '../services/collectionsApi';

const mockCollections: Collection[] = [
  {
    id: 'col-1',
    name: 'Machine Learning',
    description: 'ML books',
    item_count: 5,
    created_at: '2024-11-10T08:00:00Z',
    updated_at: '2025-01-15T14:30:00Z',
  },
  {
    id: 'col-2',
    name: 'Philosophy',
    description: '',
    item_count: 0,
    created_at: '2024-12-01T10:00:00Z',
    updated_at: '2025-01-20T09:15:00Z',
  },
];

describe('CollectionsGrid', () => {
  it('renders collection cards with names', () => {
    const onSelect = vi.fn();
    render(
      <IntlWrapper>
        <CollectionsGrid collections={mockCollections} onSelect={onSelect} />
      </IntlWrapper>
    );

    expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    expect(screen.getByText('Philosophy')).toBeInTheDocument();
  });

  it('shows description when present', () => {
    const onSelect = vi.fn();
    render(
      <IntlWrapper>
        <CollectionsGrid collections={mockCollections} onSelect={onSelect} />
      </IntlWrapper>
    );

    expect(screen.getByText('ML books')).toBeInTheDocument();
  });

  it('shows item count for each collection', () => {
    const onSelect = vi.fn();
    render(
      <IntlWrapper>
        <CollectionsGrid collections={mockCollections} onSelect={onSelect} />
      </IntlWrapper>
    );

    expect(screen.getByText('5 items')).toBeInTheDocument();
    expect(screen.getByText('0 items')).toBeInTheDocument();
  });

  it('calls onSelect with collection id when a card is clicked', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionsGrid collections={mockCollections} onSelect={onSelect} />
      </IntlWrapper>
    );

    await user.click(screen.getByText('Machine Learning'));
    expect(onSelect).toHaveBeenCalledWith('col-1');
  });

  it('shows empty message when there are no collections', () => {
    const onSelect = vi.fn();
    render(
      <IntlWrapper>
        <CollectionsGrid collections={[]} onSelect={onSelect} />
      </IntlWrapper>
    );

    expect(screen.getByText(/no collections yet/i)).toBeInTheDocument();
  });
});
