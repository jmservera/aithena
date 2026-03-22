import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import SimilarBooks from '../Components/SimilarBooks';
import BookCard from '../Components/BookCard';
import { BookResult } from '../hooks/search';
import { IntlWrapper } from './test-intl-wrapper';

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
    {
      id: 'similar-2',
      title: 'Network Protocols',
      author: 'John Smith',
      year: 2019,
      score: 0.78,
    },
  ],
};

const mockBook: BookResult = {
  id: 'book-42',
  title: 'Advanced Algorithms',
  author: 'Alice',
  year: 2021,
  document_url: '/documents/algorithms.pdf',
  highlights: [],
};

describe('SimilarBooks decoupled behavior', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders standalone with only a documentId (no PDF viewer needed)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => similarBooksResponse,
    } as Response);

    render(
      <IntlWrapper>
        <SimilarBooks documentId="book-42" onSelectBook={vi.fn()} />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Handbook')).toBeInTheDocument();
    });
    expect(screen.getByText('Network Protocols')).toBeInTheDocument();
  });

  it('accepts a null documentId without crashing', () => {
    render(
      <IntlWrapper>
        <SimilarBooks documentId={null as unknown as string} onSelectBook={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('re-fetches when documentId changes', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => similarBooksResponse,
    } as Response);

    const { rerender } = render(
      <IntlWrapper>
        <SimilarBooks documentId="book-1" onSelectBook={vi.fn()} />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Handbook')).toBeInTheDocument();
    });

    rerender(
      <IntlWrapper>
        <SimilarBooks documentId="book-2" onSelectBook={vi.fn()} />
      </IntlWrapper>
    );

    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
    });

    expect(vi.mocked(fetch)).toHaveBeenLastCalledWith(
      expect.stringContaining('/v1/books/book-2/similar'),
      expect.any(Object)
    );
  });

  it('remains visible and interactive regardless of PDF viewer state', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => similarBooksResponse,
    } as Response);

    const onSelectBook = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <SimilarBooks documentId="book-42" onSelectBook={onSelectBook} />
      </IntlWrapper>
    );

    const card = await screen.findByRole('button', {
      name: /open similar book distributed systems handbook/i,
    });

    await user.click(card);
    expect(onSelectBook).toHaveBeenCalledWith('similar-1');
  });
});

describe('BookCard onSelect prop', () => {
  it('calls onSelect when the card is clicked', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={onSelect} />
      </IntlWrapper>
    );

    const card = screen.getByRole('button', { name: /advanced algorithms/i });
    await user.click(card);

    expect(onSelect).toHaveBeenCalledWith(mockBook);
  });

  it('does not call onSelect when Open PDF button is clicked', async () => {
    const onSelect = vi.fn();
    const onOpenPdf = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={onSelect} onOpenPdf={onOpenPdf} />
      </IntlWrapper>
    );

    const pdfButton = screen.getByLabelText(/open pdf for advanced algorithms/i);
    await user.click(pdfButton);

    expect(onOpenPdf).toHaveBeenCalledWith(mockBook);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('adds selectable class when onSelect is provided', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={vi.fn()} />
      </IntlWrapper>
    );

    const card = screen.getByRole('button', { name: /advanced algorithms/i });
    expect(card).toHaveClass('book-card--selectable');
  });

  it('renders without selectable class when onSelect is not provided', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} />
      </IntlWrapper>
    );

    const card = screen.getByRole('article');
    expect(card).not.toHaveClass('book-card--selectable');
  });

  it('shows active state when isSelected is true', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={vi.fn()} isSelected={true} />
      </IntlWrapper>
    );

    const card = screen.getByRole('button', { name: /advanced algorithms/i });
    expect(card).toHaveClass('book-card--active');
  });

  it('supports keyboard activation with Enter key', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={onSelect} />
      </IntlWrapper>
    );

    const card = screen.getByRole('button', { name: /advanced algorithms/i });
    card.focus();
    await user.keyboard('{Enter}');

    expect(onSelect).toHaveBeenCalledWith(mockBook);
  });

  it('supports keyboard activation with Space key', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <BookCard book={mockBook} onSelect={onSelect} />
      </IntlWrapper>
    );

    const card = screen.getByRole('button', { name: /advanced algorithms/i });
    card.focus();
    await user.keyboard(' ');

    expect(onSelect).toHaveBeenCalledWith(mockBook);
  });
});
