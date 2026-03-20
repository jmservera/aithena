import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import CollectionDetailView from '../Components/CollectionDetailView';
import { IntlWrapper } from './test-intl-wrapper';
import { type CollectionDetail } from '../services/collectionsApi';

const mockDetail: CollectionDetail = {
  id: 'col-1',
  name: 'ML Essentials',
  description: 'Core ML texts',
  item_count: 2,
  created_at: '2024-11-10T08:00:00Z',
  updated_at: '2025-01-15T14:30:00Z',
  items: [
    {
      id: 'item-1',
      document_id: 'doc-101',
      title: 'Deep Learning',
      author: 'Ian Goodfellow',
      year: 2016,
      cover_url: null,
      note: 'Great intro.',
      added_at: '2025-01-10T10:00:00Z',
    },
    {
      id: 'item-2',
      document_id: 'doc-102',
      title: 'Pattern Recognition',
      author: 'Bishop',
      year: 2006,
      cover_url: null,
      note: '',
      added_at: '2025-01-12T11:30:00Z',
    },
  ],
};

function renderDetailView(overrides?: Partial<CollectionDetail>) {
  const detail = { ...mockDetail, ...overrides };
  const onRemoveItem = vi.fn();
  const onSaveNote = vi.fn();
  const onEdit = vi.fn();
  const onDelete = vi.fn();

  const result = render(
    <IntlWrapper>
      <CollectionDetailView
        detail={detail}
        onRemoveItem={onRemoveItem}
        onSaveNote={onSaveNote}
        onEdit={onEdit}
        onDelete={onDelete}
      />
    </IntlWrapper>
  );

  return { ...result, onRemoveItem, onSaveNote, onEdit, onDelete };
}

describe('CollectionDetailView', () => {
  it('renders the collection name and description', () => {
    renderDetailView();

    expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    expect(screen.getByText('Core ML texts')).toBeInTheDocument();
  });

  it('renders all items', () => {
    renderDetailView();

    expect(screen.getByText('Deep Learning')).toBeInTheDocument();
    expect(screen.getByText('Pattern Recognition')).toBeInTheDocument();
  });

  it('shows empty message when items is empty', () => {
    renderDetailView({ items: [], item_count: 0 });

    expect(screen.getByText(/this collection is empty/i)).toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    const { onEdit } = renderDetailView();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /edit collection/i }));
    expect(onEdit).toHaveBeenCalled();
  });

  it('calls onDelete when delete button is clicked', async () => {
    const { onDelete } = renderDetailView();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /delete collection/i }));
    expect(onDelete).toHaveBeenCalled();
  });

  it('has a working sort dropdown', () => {
    renderDetailView();

    const sortSelect = screen.getByRole('combobox');
    expect(sortSelect).toBeInTheDocument();
    // Default is "Newest first"
    expect(sortSelect).toHaveValue('added_at:desc');
  });
});
