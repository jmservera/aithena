import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import CollectionsPage from '../pages/CollectionsPage';
import { IntlWrapper } from './test-intl-wrapper';

// vi.hoisted ensures these are available when vi.mock is hoisted
const { mockCreate, mockReload } = vi.hoisted(() => ({
  mockCreate: vi.fn().mockResolvedValue({ id: 'col-new', name: 'New' }),
  mockReload: vi.fn(),
}));

vi.mock('../hooks/collections', () => ({
  useCollections: vi.fn().mockReturnValue({
    collections: [
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
        item_count: 3,
        created_at: '2024-12-01T10:00:00Z',
        updated_at: '2025-01-20T09:15:00Z',
      },
    ],
    loading: false,
    error: null,
    reload: mockReload,
    create: mockCreate,
    update: vi.fn(),
    remove: vi.fn(),
  }),
}));

function renderCollectionsPage() {
  return render(
    <IntlWrapper>
      <MemoryRouter>
        <CollectionsPage />
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('CollectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', () => {
    renderCollectionsPage();

    expect(screen.getByText('Collections')).toBeInTheDocument();
  });

  it('renders the collections grid', () => {
    renderCollectionsPage();

    expect(screen.getByText('Machine Learning')).toBeInTheDocument();
    expect(screen.getByText('Philosophy')).toBeInTheDocument();
  });

  it('has a New Collection button', () => {
    renderCollectionsPage();

    expect(screen.getByRole('button', { name: /new collection/i })).toBeInTheDocument();
  });

  it('opens create modal when New Collection is clicked', async () => {
    const user = userEvent.setup();
    renderCollectionsPage();

    await user.click(screen.getByRole('button', { name: /new collection/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText('Create Collection')).toBeInTheDocument();
  });
});
