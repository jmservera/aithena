import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import SearchPage from '../pages/SearchPage';
import { SearchResponse } from '../hooks/search';

const mockSearchResponse: SearchResponse = {
  query: 'react',
  total: 2,
  page: 1,
  limit: 10,
  results: [
    {
      id: 'book-1',
      title: 'Learning React',
      author: 'Jane Doe',
      year: 2021,
      document_url: '/documents/react.pdf',
    },
    {
      id: 'book-2',
      title: 'Advanced React Patterns',
      author: 'John Smith',
      year: 2022,
      document_url: '/documents/advanced-react.pdf',
    },
  ],
  facets: {
    author: [
      { value: 'Jane Doe', count: 1 },
      { value: 'John Smith', count: 1 },
    ],
    category: [{ value: 'Programming', count: 2 }],
    language: [],
    year: [
      { value: '2021', count: 1 },
      { value: '2022', count: 1 },
    ],
  },
};

const emptySearchResponse: SearchResponse = {
  query: 'noresults',
  total: 0,
  page: 1,
  limit: 10,
  results: [],
  facets: {},
};

const similarBooksResponse = {
  results: [
    {
      id: 'book-3',
      title: 'Semantic Search in Practice',
      author: 'Ada Lovelace',
      year: 2024,
      category: 'Programming',
      document_url: '/documents/semantic-search.pdf',
      score: 0.96,
    },
  ],
};

function renderSearchPage() {
  return render(
    <MemoryRouter>
      <SearchPage />
    </MemoryRouter>
  );
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the search input and button', () => {
    renderSearchPage();
    expect(screen.getByRole('searchbox', { name: /search query/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('shows placeholder prompt when no query has been submitted', () => {
    renderSearchPage();
    expect(screen.getByText(/enter a search term above/i)).toBeInTheDocument();
  });

  it('calls fetch and renders results after query submission', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse,
    } as Response);

    const user = userEvent.setup();
    renderSearchPage();

    await user.type(screen.getByRole('searchbox', { name: /search query/i }), 'react');
    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText('Learning React')).toBeInTheDocument();
    });

    expect(screen.getByText('Advanced React Patterns')).toBeInTheDocument();
    expect(screen.getByText(/2 results.*react/i)).toBeInTheDocument();
  });

  it('shows empty state when search returns no results', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => emptySearchResponse,
    } as Response);

    const user = userEvent.setup();
    renderSearchPage();

    await user.type(screen.getByRole('searchbox', { name: /search query/i }), 'noresults');
    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText(/no results found.*noresults/i)).toBeInTheDocument();
    });
  });

  it('shows an error message when the API call fails', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    const user = userEvent.setup();
    renderSearchPage();

    await user.type(screen.getByRole('searchbox', { name: /search query/i }), 'error');
    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows similar books after opening a PDF and updates the selected document when clicked', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSearchResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => similarBooksResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);

    const user = userEvent.setup();
    renderSearchPage();

    await user.type(screen.getByRole('searchbox', { name: /search query/i }), 'react');
    await user.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText('Learning React')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /open pdf for learning react/i }));

    await waitFor(() => {
      expect(screen.getByText(/similar books/i)).toBeInTheDocument();
    });

    const viewer = within(screen.getByRole('dialog'));
    expect(viewer.getByText('Learning React')).toBeInTheDocument();

    const similarBookButton = await screen.findByRole('button', {
      name: /open similar book semantic search in practice/i,
    });
    await user.click(similarBookButton);

    await waitFor(() => {
      expect(viewer.getByText('Semantic Search in Practice')).toBeInTheDocument();
    });
  });
});
