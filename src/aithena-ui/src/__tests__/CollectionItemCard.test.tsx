import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import CollectionItemCard from '../Components/CollectionItemCard';
import { IntlWrapper } from './test-intl-wrapper';
import { type CollectionItem } from '../services/collectionsApi';

const mockItem: CollectionItem = {
  id: 'item-1',
  document_id: 'doc-101',
  title: 'Deep Learning',
  author: 'Ian Goodfellow',
  year: 2016,
  cover_url: null,
  thumbnail_url: null,
  document_url: '/documents/abc123',
  note: 'Great introduction.',
  added_at: '2025-01-10T10:00:00Z',
};

describe('CollectionItemCard', () => {
  it('renders the item title and metadata', () => {
    render(
      <IntlWrapper>
        <CollectionItemCard item={mockItem} onRemove={vi.fn()} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByText('Deep Learning')).toBeInTheDocument();
    expect(screen.getByText('Ian Goodfellow')).toBeInTheDocument();
    expect(screen.getByText('2016')).toBeInTheDocument();
  });

  it('renders the note in the editor', () => {
    render(
      <IntlWrapper>
        <CollectionItemCard item={mockItem} onRemove={vi.fn()} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    const textarea = screen.getByRole('textbox', { name: /note/i });
    expect(textarea).toHaveValue('Great introduction.');
  });

  it('shows remove button that requires confirmation', async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionItemCard item={mockItem} onRemove={onRemove} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    const removeBtn = screen.getByRole('button', { name: /remove deep learning/i });
    // First click shows confirm
    await user.click(removeBtn);
    expect(onRemove).not.toHaveBeenCalled();
    expect(screen.getByText('Confirm')).toBeInTheDocument();

    // Second click actually removes
    await user.click(removeBtn);
    expect(onRemove).toHaveBeenCalledWith('item-1');
  });

  it('cancel button resets confirmation state', async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionItemCard item={mockItem} onRemove={onRemove} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    // Click remove to trigger confirm state
    const removeBtn = screen.getByRole('button', { name: /remove deep learning/i });
    await user.click(removeBtn);
    expect(screen.getByText('Confirm')).toBeInTheDocument();

    // Click cancel
    await user.click(screen.getByText('Cancel'));
    // Should show Remove again
    expect(screen.getByText('Remove')).toBeInTheDocument();
  });

  it('renders Open PDF button when document_url and onOpenPdf are provided', () => {
    const onOpenPdf = vi.fn();

    render(
      <IntlWrapper>
        <CollectionItemCard
          item={mockItem}
          onRemove={vi.fn()}
          onSaveNote={vi.fn()}
          onOpenPdf={onOpenPdf}
        />
      </IntlWrapper>
    );

    expect(screen.getByRole('button', { name: /open pdf/i })).toBeInTheDocument();
  });

  it('calls onOpenPdf when Open PDF button is clicked', async () => {
    const onOpenPdf = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionItemCard
          item={mockItem}
          onRemove={vi.fn()}
          onSaveNote={vi.fn()}
          onOpenPdf={onOpenPdf}
        />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /open pdf/i }));
    expect(onOpenPdf).toHaveBeenCalledWith(mockItem);
  });

  it('does not render Open PDF button when document_url is null', () => {
    const itemWithoutPdf = { ...mockItem, document_url: null };

    render(
      <IntlWrapper>
        <CollectionItemCard
          item={itemWithoutPdf}
          onRemove={vi.fn()}
          onSaveNote={vi.fn()}
          onOpenPdf={vi.fn()}
        />
      </IntlWrapper>
    );

    expect(screen.queryByRole('button', { name: /open pdf/i })).not.toBeInTheDocument();
  });

  it('renders placeholder thumbnail when thumbnail_url is null', () => {
    render(
      <IntlWrapper>
        <CollectionItemCard item={mockItem} onRemove={vi.fn()} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    const placeholder = screen
      .getByTestId(`collection-item-${mockItem.id}`)
      .querySelector('.book-card-thumbnail--placeholder');
    expect(placeholder).toBeInTheDocument();
  });

  it('renders thumbnail image when thumbnail_url is provided', () => {
    const itemWithThumb = { ...mockItem, thumbnail_url: '/thumbnails/cover.jpg' };

    render(
      <IntlWrapper>
        <CollectionItemCard item={itemWithThumb} onRemove={vi.fn()} onSaveNote={vi.fn()} />
      </IntlWrapper>
    );

    const img = screen.getByRole('img', { name: 'Deep Learning' });
    expect(img).toHaveAttribute('src', '/thumbnails/cover.jpg');
  });
});
