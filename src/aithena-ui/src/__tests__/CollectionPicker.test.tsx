import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import CollectionPicker from '../Components/CollectionPicker';
import { IntlWrapper } from './test-intl-wrapper';

// Mock the service module
vi.mock('../services/collectionsApi', () => ({
  fetchCollections: vi.fn().mockResolvedValue([
    {
      id: 'col-1',
      name: 'Machine Learning',
      description: '',
      item_count: 5,
      created_at: '2024-11-10T08:00:00Z',
      updated_at: '2025-01-15T14:30:00Z',
    },
    {
      id: 'col-2',
      name: 'Philosophy',
      description: '',
      item_count: 3,
      created_at: '2024-12-01T10:00:00Z',
      updated_at: '2025-01-20T09:15:00Z',
    },
  ]),
}));

describe('CollectionPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the toggle button', () => {
    render(
      <IntlWrapper>
        <CollectionPicker onSelect={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByRole('button', { name: /add to collection/i })).toBeInTheDocument();
  });

  it('opens dropdown and shows collections when clicked', async () => {
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionPicker onSelect={vi.fn()} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /add to collection/i }));

    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
      expect(screen.getByText('Philosophy')).toBeInTheDocument();
    });
  });

  it('filters collections by search query', async () => {
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionPicker onSelect={vi.fn()} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /add to collection/i }));

    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    });

    await user.type(screen.getByRole('textbox', { name: /search collections/i }), 'phil');

    expect(screen.queryByText('Machine Learning')).not.toBeInTheDocument();
    expect(screen.getByText('Philosophy')).toBeInTheDocument();
  });

  it('calls onSelect when a collection is chosen', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionPicker onSelect={onSelect} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /add to collection/i }));

    await waitFor(() => {
      expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Machine Learning'));
    expect(onSelect).toHaveBeenCalledWith('col-1');
  });

  it('excludes collections by excludeIds', async () => {
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionPicker onSelect={vi.fn()} excludeIds={['col-1']} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /add to collection/i }));

    await waitFor(() => {
      expect(screen.getByText('Philosophy')).toBeInTheDocument();
    });

    expect(screen.queryByText('Machine Learning')).not.toBeInTheDocument();
  });
});
