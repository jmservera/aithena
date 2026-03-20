import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AddToCollectionModal from '../Components/AddToCollectionModal';
import { IntlWrapper } from './test-intl-wrapper';

vi.mock('../services/collectionsApi', () => ({
  fetchCollections: vi.fn(),
  addItemToCollection: vi.fn(),
  createCollection: vi.fn(),
}));

import {
  fetchCollections,
  addItemToCollection,
  createCollection,
} from '../services/collectionsApi';

const mockCollections = [
  {
    id: 'col-1',
    name: 'ML Essentials',
    description: 'ML books',
    item_count: 3,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'col-2',
    name: 'Philosophy',
    description: '',
    item_count: 1,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

describe('AddToCollectionModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchCollections).mockResolvedValue(mockCollections);
    vi.mocked(addItemToCollection).mockResolvedValue({
      id: 'item-new',
      document_id: 'doc-1',
      title: 'Test',
      note: '',
      added_at: new Date().toISOString(),
    });
    vi.mocked(createCollection).mockResolvedValue({
      id: 'col-new',
      name: 'New Collection',
      description: '',
      item_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  });

  it('does not render when closed', () => {
    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={false}
          onClose={vi.fn()}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders collection list when open', async () => {
    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={vi.fn()}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    });
    expect(screen.getByText('Philosophy')).toBeInTheDocument();
  });

  it('filters collections by search query', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={vi.fn()}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/search collections/i), 'Phil');
    expect(screen.queryByText('ML Essentials')).not.toBeInTheDocument();
    expect(screen.getByText('Philosophy')).toBeInTheDocument();
  });

  it('calls addItemToCollection and onSuccess when collection is selected', async () => {
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={onClose}
          documentIds={['doc-1']}
          onSuccess={onSuccess}
        />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    });

    await user.click(screen.getByText('ML Essentials'));

    await waitFor(() => {
      expect(addItemToCollection).toHaveBeenCalledWith('col-1', 'doc-1');
      expect(onSuccess).toHaveBeenCalledWith('ML Essentials', 1);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('shows create form when "Create new collection" is clicked', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={vi.fn()}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    });

    await user.click(screen.getByText(/create new collection/i));
    expect(screen.getByPlaceholderText(/collection name/i)).toBeInTheDocument();
    expect(screen.getByText(/create & add/i)).toBeInTheDocument();
  });

  it('creates collection and adds items when create form is submitted', async () => {
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={onClose}
          documentIds={['doc-1']}
          onSuccess={onSuccess}
        />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    });

    await user.click(screen.getByText(/create new collection/i));
    await user.type(screen.getByPlaceholderText(/collection name/i), 'New Collection');
    await user.click(screen.getByText(/create & add/i));

    await waitFor(() => {
      expect(createCollection).toHaveBeenCalledWith({ name: 'New Collection' });
      expect(addItemToCollection).toHaveBeenCalledWith('col-new', 'doc-1');
      expect(onSuccess).toHaveBeenCalledWith('New Collection', 1);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('calls onClose when cancel is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={onClose}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    const cancelButtons = screen.getAllByText(/cancel/i);
    await user.click(cancelButtons[cancelButtons.length - 1]);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows count message for multiple documents', async () => {
    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={vi.fn()}
          documentIds={['doc-1', 'doc-2', 'doc-3']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText(/adding 3 books/i)).toBeInTheDocument();
    });
  });

  it('closes on Escape key', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <AddToCollectionModal
          open={true}
          onClose={onClose}
          documentIds={['doc-1']}
          onSuccess={vi.fn()}
        />
      </IntlWrapper>
    );

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});
