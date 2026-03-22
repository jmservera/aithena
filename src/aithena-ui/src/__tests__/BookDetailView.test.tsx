import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import BookDetailView from '../Components/BookDetailView';
import { IntlWrapper } from './test-intl-wrapper';
import { AuthContext, AuthContextValue } from '../contexts/AuthContext';
import { BookResult } from '../hooks/search';

const mockBook: BookResult = {
  id: 'book-123',
  title: 'Advanced Systems Design',
  author: 'Alice Smith',
  year: 2023,
  category: 'Engineering',
  language: 'English',
  series: 'Tech Library',
  page_count: 342,
  file_size: 5242880,
  folder_path: '/library/engineering',
  file_path: '/library/engineering/advanced-systems.pdf',
  document_url: '/documents/advanced-systems.pdf',
  is_chunk: false,
  highlights: [],
};

const mockChunkBook: BookResult = {
  ...mockBook,
  id: 'chunk-456',
  is_chunk: true,
  chunk_text: 'This section discusses distributed consensus algorithms.',
  page_start: 42,
  page_end: 45,
};

function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    clearError: vi.fn(),
    ...overrides,
  };
}

function renderWithProviders(
  ui: React.ReactElement,
  authValue: AuthContextValue = createAuthValue()
) {
  return render(
    <AuthContext.Provider value={authValue}>
      <IntlWrapper>{ui}</IntlWrapper>
    </AuthContext.Provider>
  );
}

describe('BookDetailView', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.style.overflow = '';
  });

  describe('with initialData', () => {
    it('renders book title and author from initial data', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      // Title appears in both toolbar and header
      const titles = screen.getAllByText('Advanced Systems Design');
      expect(titles.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
      expect(screen.getByText('2023')).toBeInTheDocument();
    });

    it('renders metadata grid with category, language, series, page count', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('English')).toBeInTheDocument();
      expect(screen.getByText('Tech Library')).toBeInTheDocument();
      expect(screen.getByText('342')).toBeInTheDocument();
    });

    it('renders formatted file size', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByText('5.0 MB')).toBeInTheDocument();
    });

    it('renders folder path', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByText('/library/engineering')).toBeInTheDocument();
    });

    it('does not fetch from API when initialData is provided', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      // Only the SimilarBooks component fetches (for similar books), not the detail
      const fetchCalls = vi.mocked(fetch).mock.calls;
      const bookDetailCalls = fetchCalls.filter(
        (call) =>
          typeof call[0] === 'string' &&
          call[0].includes('/v1/books/book-123') &&
          !call[0].includes('/similar')
      );
      expect(bookDetailCalls).toHaveLength(0);
    });
  });

  describe('data fetching', () => {
    it('fetches book detail from API when no initialData is provided', async () => {
      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = typeof input === 'string' ? input : input instanceof Request ? input.url : '';
        if (url.includes('/v1/books/book-123') && !url.includes('/similar')) {
          return { ok: true, json: async () => mockBook } as Response;
        }
        return { ok: true, json: async () => ({ results: [] }) } as Response;
      });

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getAllByText('Advanced Systems Design').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows loading state while fetching', () => {
      vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('shows error state when fetch fails', async () => {
      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = typeof input === 'string' ? input : input instanceof Request ? input.url : '';
        if (url.includes('/v1/books/') && !url.includes('/similar')) {
          return { ok: false, status: 500 } as Response;
        }
        return { ok: true, json: async () => ({ results: [] }) } as Response;
      });

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });
  });

  describe('chunk text preview', () => {
    it('renders chunk text when book is a chunk', () => {
      renderWithProviders(
        <BookDetailView
          bookId="chunk-456"
          initialData={mockChunkBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(
        screen.getByText('This section discusses distributed consensus algorithms.')
      ).toBeInTheDocument();
    });

    it('renders page range for chunk text', () => {
      renderWithProviders(
        <BookDetailView
          bookId="chunk-456"
          initialData={mockChunkBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByText(/pages 42/i)).toBeInTheDocument();
    });

    it('does not render chunk section for non-chunk books', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(
        screen.queryByText('This section discusses distributed consensus algorithms.')
      ).not.toBeInTheDocument();
    });
  });

  describe('action buttons', () => {
    it('renders Open PDF button and calls onOpenPdf when clicked', async () => {
      const user = userEvent.setup();
      const onOpenPdf = vi.fn();

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={onOpenPdf}
          onSelectSimilarBook={vi.fn()}
        />
      );

      const pdfBtn = screen.getByRole('button', { name: /open pdf/i });
      await user.click(pdfBtn);

      expect(onOpenPdf).toHaveBeenCalledWith(mockBook);
    });

    it('does not render edit metadata button for non-admin users', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        createAuthValue({ user: { id: 1, username: 'user', role: 'user' } })
      );

      expect(screen.queryByLabelText(/edit metadata/i)).not.toBeInTheDocument();
    });

    it('renders edit metadata button for admin users', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        createAuthValue({ user: { id: 1, username: 'admin', role: 'admin' } })
      );

      expect(screen.getByLabelText(/edit metadata/i)).toBeInTheDocument();
    });
  });

  describe('modal behavior', () => {
    it('has dialog role with aria-modal', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('calls onClose when ESC is pressed', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={onClose}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      await user.keyboard('{Escape}');
      expect(onClose).toHaveBeenCalled();
    });

    it('calls onClose when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={onClose}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      const dialog = screen.getByRole('dialog');
      await user.click(dialog);
      expect(onClose).toHaveBeenCalled();
    });

    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={onClose}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      const closeBtn = screen.getByLabelText(/close book details/i);
      await user.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    });

    it('locks body scroll on mount', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(document.body.style.overflow).toBe('hidden');
    });
  });

  describe('similar books', () => {
    it('renders the SimilarBooks section', () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(screen.getByRole('region', { name: /similar books/i })).toBeInTheDocument();
    });
  });

  describe('optional metadata', () => {
    it('hides metadata fields that are not present', () => {
      const minimalBook: BookResult = {
        id: 'minimal-1',
        title: 'Minimal Book',
      };

      renderWithProviders(
        <BookDetailView
          bookId="minimal-1"
          initialData={minimalBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      // Title appears in both toolbar and header
      expect(screen.getAllByText('Minimal Book').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/unknown author/i)).toBeInTheDocument();
      // Metadata labels should not be rendered for missing fields
      expect(screen.queryByText(/category:/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/language:/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/series:/i)).not.toBeInTheDocument();
    });
  });
});
