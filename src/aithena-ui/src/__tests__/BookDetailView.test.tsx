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

const adminAuth = createAuthValue({
  user: { id: 1, username: 'admin', role: 'admin' },
  isAuthenticated: true,
});

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
        adminAuth
      );

      expect(screen.getByLabelText(/edit metadata/i)).toBeInTheDocument();
    });
  });

  describe('inline edit mode', () => {
    it('enters edit mode when admin clicks edit metadata button', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      const editBtn = screen.getByLabelText(/edit metadata/i);
      await user.click(editBtn);

      // Edit form fields should appear
      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/author/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/year/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/series/i)).toBeInTheDocument();
    });

    it('hides edit metadata button while in edit mode', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      const editBtn = screen.getByLabelText(/edit metadata/i);
      await user.click(editBtn);

      expect(screen.queryByLabelText(/edit metadata/i)).not.toBeInTheDocument();
    });

    it('hides read-only metadata in edit mode', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));

      // Read-only header section should be hidden
      expect(screen.queryByText('Alice Smith')).not.toBeInTheDocument();
      // Read-only metadata grid items are hidden
      expect(screen.queryByText('English')).not.toBeInTheDocument();
    });

    it('populates edit fields with current book data', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));

      expect(screen.getByLabelText(/title/i)).toHaveValue('Advanced Systems Design');
      expect(screen.getByLabelText(/author/i)).toHaveValue('Alice Smith');
      expect(screen.getByLabelText(/year/i)).toHaveValue(2023);
      expect(screen.getByLabelText(/category/i)).toHaveValue('Engineering');
      expect(screen.getByLabelText(/series/i)).toHaveValue('Tech Library');
    });

    it('renders Save and Cancel buttons in edit mode', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));

      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('exits edit mode when Cancel is clicked', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));
      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      // Should be back in read-only mode
      expect(screen.queryByLabelText(/title/i)).not.toBeInTheDocument();
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
      expect(screen.getByLabelText(/edit metadata/i)).toBeInTheDocument();
    });

    it('exits edit mode on ESC without closing modal', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={onClose}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));
      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();

      await user.keyboard('{Escape}');

      // Should exit edit mode but NOT close the modal
      expect(onClose).not.toHaveBeenCalled();
      expect(screen.queryByLabelText(/title/i)).not.toBeInTheDocument();
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    it('disables Save button when no changes made', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));

      expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
    });

    it('enables Save button after editing a field', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Updated Title');

      expect(screen.getByRole('button', { name: /save/i })).not.toBeDisabled();
    });

    it('saves changes and shows success toast', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = typeof input === 'string' ? input : input instanceof Request ? input.url : '';
        if (url.includes('/metadata')) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (url.includes('/v1/books/book-123') && !url.includes('/similar')) {
          return {
            ok: true,
            json: async () => ({ ...mockBook, title: 'Updated Title' }),
          } as Response;
        }
        return { ok: true, json: async () => ({ results: [], facets: {} }) } as Response;
      });

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Updated Title');
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Toast should appear
      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
      });
    });

    it('shows API error when save fails', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = typeof input === 'string' ? input : input instanceof Request ? input.url : '';
        if (url.includes('/metadata')) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ detail: 'Server error' }),
          } as Response;
        }
        return { ok: true, json: async () => ({ results: [], facets: {} }) } as Response;
      });

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Changed');
      await user.click(screen.getByRole('button', { name: /save/i }));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Server error')).toBeInTheDocument();
      });
    });

    it('keeps Open PDF and external link visible in edit mode', async () => {
      const user = userEvent.setup();

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], facets: {} }),
      } as Response);

      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />,
        adminAuth
      );

      await user.click(screen.getByLabelText(/edit metadata/i));

      expect(screen.getByRole('button', { name: /open pdf/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /open in new tab/i })).toBeInTheDocument();
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

  describe('accessibility – focus trap and ARIA', () => {
    it('dialog has aria-labelledby pointing to the title', () => {
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
      const labelledById = dialog.getAttribute('aria-labelledby');
      expect(labelledById).toBeTruthy();
      // The referenced element should contain the book title
      const labelEl = document.getElementById(labelledById!);
      expect(labelEl).not.toBeNull();
      expect(labelEl!.textContent).toContain('Advanced Systems Design');
    });

    it('restores body scroll overflow on unmount', () => {
      document.body.style.overflow = 'auto';

      const { unmount } = renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      expect(document.body.style.overflow).toBe('hidden');

      unmount();

      expect(document.body.style.overflow).toBe('auto');
    });

    it('sets initial focus to the close button on mount', () => {
      renderWithProviders(
        <BookDetailView
          bookId="book-123"
          initialData={mockBook}
          onClose={vi.fn()}
          onOpenPdf={vi.fn()}
          onSelectSimilarBook={vi.fn()}
        />
      );

      const closeBtn = screen.getByLabelText(/close book details/i);
      expect(document.activeElement).toBe(closeBtn);
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
