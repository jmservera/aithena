import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import BookCard from '../Components/BookCard';
import { BookResult } from '../hooks/search';
import { IntlWrapper } from './test-intl-wrapper';

const baseBook: BookResult = {
  id: 'doc-1',
  title: 'Deep Learning Fundamentals',
  author: 'Jane Doe',
  year: 2023,
  document_url: '/documents/deep-learning.pdf',
};

const chunkBook: BookResult = {
  ...baseBook,
  is_chunk: true,
  chunk_text:
    'Neural networks learn hierarchical representations of data through multiple layers of nonlinear transformations.',
  page_start: 3,
  page_end: 4,
};

describe('BookCard – chunk text display', () => {
  it('renders chunk text when is_chunk is true and chunk_text is present', () => {
    render(
      <IntlWrapper>
        <BookCard book={chunkBook} />
      </IntlWrapper>
    );

    expect(screen.getByText(/Matching text/)).toBeInTheDocument();
    // chunk_text is truncated to ~20 visible characters with an ellipsis
    const chunkContent = screen.getByText(/Neural networks lear/);
    expect(chunkContent).toBeInTheDocument();
    expect(chunkContent.textContent).toContain('…');
  });

  it('shows page range when page_start and page_end differ', () => {
    render(
      <IntlWrapper>
        <BookCard book={chunkBook} />
      </IntlWrapper>
    );

    expect(screen.getByText(/Pages 3–4/)).toBeInTheDocument();
  });

  it('shows single page when page_start equals page_end', () => {
    const singlePageChunk: BookResult = {
      ...chunkBook,
      page_start: 7,
      page_end: 7,
    };

    render(
      <IntlWrapper>
        <BookCard book={singlePageChunk} />
      </IntlWrapper>
    );

    expect(screen.getByText(/Page 7/)).toBeInTheDocument();
  });

  it('does not render chunk section when is_chunk is false', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.queryByText(/Matching text/)).not.toBeInTheDocument();
  });

  it('does not render chunk section when chunk_text is empty string', () => {
    const emptyChunk: BookResult = {
      ...baseBook,
      is_chunk: true,
      chunk_text: '',
    };

    render(
      <IntlWrapper>
        <BookCard book={emptyChunk} />
      </IntlWrapper>
    );

    expect(screen.queryByText(/Matching text/)).not.toBeInTheDocument();
  });

  it('does not render chunk section when chunk_text is absent', () => {
    const noTextChunk: BookResult = {
      ...baseBook,
      is_chunk: true,
    };

    render(
      <IntlWrapper>
        <BookCard book={noTextChunk} />
      </IntlWrapper>
    );

    expect(screen.queryByText(/Matching text/)).not.toBeInTheDocument();
  });

  it('omits page range when page_start and page_end are not provided', () => {
    const noPageChunk: BookResult = {
      ...baseBook,
      is_chunk: true,
      chunk_text: 'Some matching content from the document.',
    };

    render(
      <IntlWrapper>
        <BookCard book={noPageChunk} />
      </IntlWrapper>
    );

    expect(screen.getByText(/Matching text/)).toBeInTheDocument();
    // The text is truncated to ~20 chars, so partial match
    expect(screen.getByText(/Some matching conten/)).toBeInTheDocument();
    expect(screen.queryByText(/Pages/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Page \d/)).not.toBeInTheDocument();
  });

  it('still renders keyword highlights alongside chunk text', () => {
    const chunkWithHighlights: BookResult = {
      ...chunkBook,
      highlights: ['This is a <em>keyword</em> match'],
    };

    render(
      <IntlWrapper>
        <BookCard book={chunkWithHighlights} onOpenPdf={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByText(/Matching text/)).toBeInTheDocument();
    expect(screen.getByText(/keyword/)).toBeInTheDocument();
  });
});
