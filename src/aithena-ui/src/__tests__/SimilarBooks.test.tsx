import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import SimilarBooks from '../Components/SimilarBooks';

const similarBooksResponse = {
  results: [
    {
      id: 'similar-1',
      title: 'Distributed Systems Handbook',
      author: 'Jane Doe',
      year: 2020,
      category: 'Engineering',
      document_url: '/documents/distributed-systems.pdf',
      score: 0.91,
    },
  ],
};

describe('SimilarBooks', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders similar books returned by the API', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => similarBooksResponse,
    } as Response);

    render(<SimilarBooks documentId="book-1" onSelectBook={vi.fn()} />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading similar books/i);

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Handbook')).toBeInTheDocument();
    });

    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('91% match')).toBeInTheDocument();
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining('/v1/books/book-1/similar?limit=5&min_score=0'),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('shows the empty state when no similar books are found', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: [] }),
    } as Response);

    render(<SimilarBooks documentId="book-1" onSelectBook={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/no similar books found/i)).toBeInTheDocument();
    });
  });

  it('calls onSelectBook when a similar book card is clicked', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => similarBooksResponse,
    } as Response);

    const onSelectBook = vi.fn();
    const user = userEvent.setup();
    render(<SimilarBooks documentId="book-1" onSelectBook={onSelectBook} />);

    const card = await screen.findByRole('button', {
      name: /open similar book distributed systems handbook/i,
    });
    await user.click(card);

    expect(onSelectBook).toHaveBeenCalledWith('similar-1');
  });

  it('shows a friendly error message when the request fails', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    render(<SimilarBooks documentId="book-1" onSelectBook={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/couldn’t load similar books/i);
    });
  });
});
