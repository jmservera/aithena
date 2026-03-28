import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import CollectionDetailPage from '../pages/CollectionDetailPage';
import { IntlWrapper } from './test-intl-wrapper';

const { mockRemoveItem, mockSaveNote, mockUpdateMeta, mockDeleteCollection, mockReload } =
  vi.hoisted(() => ({
    mockRemoveItem: vi.fn(),
    mockSaveNote: vi.fn(),
    mockUpdateMeta: vi.fn(),
    mockDeleteCollection: vi.fn(),
    mockReload: vi.fn(),
  }));

vi.mock('../hooks/collections', () => ({
  useCollectionDetail: vi.fn().mockReturnValue({
    detail: {
      id: 'col-1',
      name: 'ML Essentials',
      description: 'Core ML texts',
      item_count: 1,
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
          thumbnail_url: null,
          document_url: '/documents/abc123',
          note: 'Great intro.',
          added_at: '2025-01-10T10:00:00Z',
        },
      ],
    },
    loading: false,
    error: null,
    reload: mockReload,
    removeItem: mockRemoveItem,
    saveNote: mockSaveNote,
    updateMeta: mockUpdateMeta,
    deleteCollection: mockDeleteCollection,
  }),
  useAutoSaveNote: vi.fn().mockReturnValue({
    debouncedSave: vi.fn(),
    saving: false,
  }),
}));

function renderDetailPage() {
  return render(
    <IntlWrapper>
      <MemoryRouter initialEntries={['/collections/col-1']}>
        <Routes>
          <Route path="/collections/:id" element={<CollectionDetailPage />} />
          <Route path="/collections" element={<div>Collections List</div>} />
        </Routes>
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('CollectionDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the collection detail', () => {
    renderDetailPage();

    expect(screen.getByText('ML Essentials')).toBeInTheDocument();
    expect(screen.getByText('Core ML texts')).toBeInTheDocument();
    expect(screen.getByText('Deep Learning')).toBeInTheDocument();
  });

  it('has a back button', () => {
    renderDetailPage();

    expect(screen.getByRole('button', { name: /back to collections/i })).toBeInTheDocument();
  });

  it('opens edit modal when edit is clicked', async () => {
    const user = userEvent.setup();
    renderDetailPage();

    await user.click(screen.getByRole('button', { name: /edit collection/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText('Edit Collection')).toBeInTheDocument();
  });

  it('opens delete confirmation when delete is clicked', async () => {
    const user = userEvent.setup();
    renderDetailPage();

    await user.click(screen.getByRole('button', { name: /delete collection/i }));

    await waitFor(() => {
      expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    });
    expect(screen.getByText('Delete Collection')).toBeInTheDocument();
  });
});
