import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import LibraryPage from '../pages/LibraryPage';
import { LibraryResponse } from '../hooks/library';
import { IntlWrapper } from './test-intl-wrapper';

const mockLibraryResponse: LibraryResponse = {
  total: 3,
  page: 1,
  limit: 20,
  results: [
    {
      id: 'book-1',
      title: 'Introduction to JavaScript',
      author: 'Jane Doe',
      year: 2020,
      category: 'Programming',
      language: 'English',
      document_url: '/documents/intro-js.pdf',
    },
    {
      id: 'book-2',
      title: 'Python for Beginners',
      author: 'John Smith',
      year: 2021,
      category: 'Programming',
      language: 'English',
      document_url: '/documents/python-beginner.pdf',
    },
    {
      id: 'book-3',
      title: 'Data Structures',
      author: 'Alice Johnson',
      year: 2022,
      category: 'Computer Science',
      language: 'English',
      document_url: '/documents/data-structures.pdf',
    },
  ],
  facets: {
    author: [
      { value: 'Jane Doe', count: 1 },
      { value: 'John Smith', count: 1 },
      { value: 'Alice Johnson', count: 1 },
    ],
    category: [
      { value: 'Programming', count: 2 },
      { value: 'Computer Science', count: 1 },
    ],
    language: [{ value: 'English', count: 3 }],
    year: [
      { value: '2020', count: 1 },
      { value: '2021', count: 1 },
      { value: '2022', count: 1 },
    ],
  },
};

const emptyLibraryResponse: LibraryResponse = {
  total: 0,
  page: 1,
  limit: 20,
  results: [],
  facets: {},
};

function renderLibraryPage() {
  return render(
    <IntlWrapper>
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('LibraryPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the library title', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();
    expect(screen.getByText('📖 Library')).toBeInTheDocument();
  });

  it('fetches and displays books on mount', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('Introduction to JavaScript')).toBeInTheDocument();
      expect(screen.getByText('Python for Beginners')).toBeInTheDocument();
      expect(screen.getByText('Data Structures')).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/books'),
      expect.any(Object)
    );
  });

  it('displays the total count of books', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('3 books in collection')).toBeInTheDocument();
    });
  });

  it('displays empty state when no books are available', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(emptyLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('No books found.')).toBeInTheDocument();
    });
  });

  it('allows sorting by different fields', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('Introduction to JavaScript')).toBeInTheDocument();
    });

    const sortSelect = screen.getByLabelText('Sort:');
    await userEvent.selectOptions(sortSelect, 'author_s asc');

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('sort_by=author&sort_order=asc'),
        expect.any(Object)
      );
    });
  });

  it('allows filtering by facets', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('Introduction to JavaScript')).toBeInTheDocument();
    });

    const programmingCheckbox = screen.getByRole('checkbox', { name: /Programming/ });
    await userEvent.click(programmingCheckbox);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('fq_category=Programming'),
        expect.any(Object)
      );
    });
  });

  it('displays error state when fetch fails', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch books/i)).toBeInTheDocument();
    });
  });

  it('shows pagination when there are multiple pages', async () => {
    const largeLibraryResponse = {
      ...mockLibraryResponse,
      total: 100,
      limit: 10,
    };

    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(largeLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByLabelText('Search results pagination')).toBeInTheDocument();
    });

    expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
  });

  it('updates page size when limit is changed', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockLibraryResponse),
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    renderLibraryPage();

    await waitFor(() => {
      expect(screen.getByText('Introduction to JavaScript')).toBeInTheDocument();
    });

    const limitSelect = screen.getByLabelText('Per page:');
    await userEvent.selectOptions(limitSelect, '50');

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('page_size=50'),
        expect.any(Object)
      );
    });
  });
});
