import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';

import BookCard from '../Components/BookCard';
import { BookResult } from '../hooks/search';
import { IntlWrapper } from './test-intl-wrapper';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const baseBook: BookResult = {
  id: 'doc-1',
  title: 'React Patterns',
  author: 'Jane Doe',
  year: 2022,
  category: 'Programming',
  series: 'Tech',
  document_url: '/documents/react.pdf',
  file_path: 'en/Programming/react.pdf',
  page_count: 350,
};

const bookWithPageRange: BookResult = {
  ...baseBook,
  id: 'doc-page-range',
  pages: [42, 55],
};

const bookWithSinglePage: BookResult = {
  ...baseBook,
  id: 'doc-single-page',
  pages: [7, 7],
};

const bookWithHighlights: BookResult = {
  ...baseBook,
  id: 'doc-highlights',
  highlights: ['<em>React</em> component pattern', 'state <em>management</em>'],
};

const bookWithChunkHighlights: BookResult = {
  ...baseBook,
  id: 'doc-chunk-hl',
  highlights: ['<em>chunk</em> text from page five'],
  pages: [5, 6],
};

const minimalBook: BookResult = {
  id: 'doc-minimal',
  title: 'Untitled',
};

// ---------------------------------------------------------------------------
// Page range display (#813)
// ---------------------------------------------------------------------------

describe('BookCard – page range display', () => {
  it('renders page range when pages span multiple pages', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithPageRange} />
      </IntlWrapper>
    );

    const meta = screen.getByText(/42/);
    expect(meta).toBeInTheDocument();
    expect(meta.closest('.book-found-pages')).not.toBeNull();
  });

  it('renders single page label when page_start equals page_end', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithSinglePage} />
      </IntlWrapper>
    );

    const meta = screen.getByText(/7/);
    expect(meta).toBeInTheDocument();
    expect(meta.closest('.book-found-pages')).not.toBeNull();
  });

  it('does not render page range when pages is null', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.queryByText(/found on page/i)).not.toBeInTheDocument();
    const article = screen.getByRole('article');
    expect(within(article).queryByText(/\.book-found-pages/)).not.toBeInTheDocument();
  });

  it('does not render page range when pages is undefined', () => {
    render(
      <IntlWrapper>
        <BookCard book={minimalBook} />
      </IntlWrapper>
    );

    const article = screen.getByRole('article');
    const foundPages = article.querySelector('.book-found-pages');
    expect(foundPages).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Highlight rendering (#813)
// ---------------------------------------------------------------------------

describe('BookCard – highlights', () => {
  it('renders highlight snippets with sanitised HTML', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithHighlights} />
      </IntlWrapper>
    );

    const snippets = screen.getAllByText(/React|management/);
    expect(snippets.length).toBeGreaterThanOrEqual(1);

    const highlightContainer = document.querySelector('.book-highlights');
    expect(highlightContainer).not.toBeNull();
    expect(highlightContainer!.querySelectorAll('.book-highlight-snippet').length).toBe(2);
  });

  it('wraps highlight text with <em> tags after sanitisation', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithHighlights} />
      </IntlWrapper>
    );

    const snippetElements = document.querySelectorAll('.book-highlight-snippet');
    const firstSnippetHtml = snippetElements[0].innerHTML;
    expect(firstSnippetHtml).toContain('<em>');
    expect(firstSnippetHtml).toContain('</em>');
  });

  it('does not render highlights section when no highlights', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(document.querySelector('.book-highlights')).toBeNull();
  });

  it('renders both chunk page range and highlights together', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithChunkHighlights} />
      </IntlWrapper>
    );

    expect(document.querySelector('.book-found-pages')).not.toBeNull();
    expect(document.querySelector('.book-highlights')).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Metadata and general rendering (#813)
// ---------------------------------------------------------------------------

describe('BookCard – metadata display', () => {
  it('renders author, year, category, series, page count', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('2022')).toBeInTheDocument();
    expect(screen.getByText('Programming')).toBeInTheDocument();
    expect(screen.getByText('Tech')).toBeInTheDocument();
    expect(screen.getByText('350')).toBeInTheDocument();
  });

  it('renders file path in footer', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.getByText('en/Programming/react.pdf')).toBeInTheDocument();
  });

  it('renders open PDF button when document_url and onOpenPdf are set', () => {
    const onOpenPdf = vi.fn();
    render(
      <IntlWrapper>
        <BookCard book={baseBook} onOpenPdf={onOpenPdf} />
      </IntlWrapper>
    );

    const pdfBtn = screen.getByRole('button', { name: /open pdf/i });
    expect(pdfBtn).toBeInTheDocument();
    expect(pdfBtn).toHaveAttribute('aria-haspopup', 'dialog');
  });

  it('calls onOpenPdf with the book when PDF button is clicked', async () => {
    const user = userEvent.setup();
    const onOpenPdf = vi.fn();
    render(
      <IntlWrapper>
        <BookCard book={baseBook} onOpenPdf={onOpenPdf} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /open pdf/i }));
    expect(onOpenPdf).toHaveBeenCalledWith(baseBook);
  });

  it('does not render open PDF button when document_url is absent', () => {
    render(
      <IntlWrapper>
        <BookCard book={minimalBook} onOpenPdf={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('button', { name: /open pdf/i })).not.toBeInTheDocument();
  });

  it('does not render open PDF button when onOpenPdf is not provided', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('button', { name: /open pdf/i })).not.toBeInTheDocument();
  });

  it('omits optional metadata fields when absent', () => {
    render(
      <IntlWrapper>
        <BookCard book={minimalBook} />
      </IntlWrapper>
    );

    expect(screen.getByText('Untitled')).toBeInTheDocument();
    expect(screen.queryByText('Unknown')).not.toBeInTheDocument();
    const metaItems = document.querySelectorAll('.book-meta-item');
    expect(metaItems.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Selection mode (#823 gap-fill)
// ---------------------------------------------------------------------------

describe('BookCard – selection mode', () => {
  it('renders checkbox when selectionMode is true', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} selectionMode={true} onToggleSelect={vi.fn()} />
      </IntlWrapper>
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
  });

  it('calls onToggleSelect with book id when checkbox is clicked', async () => {
    const user = userEvent.setup();
    const onToggleSelect = vi.fn();

    render(
      <IntlWrapper>
        <BookCard book={baseBook} selectionMode={true} onToggleSelect={onToggleSelect} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('checkbox'));
    expect(onToggleSelect).toHaveBeenCalledWith('doc-1');
  });

  it('checkbox reflects isChecked prop', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} selectionMode={true} isChecked={true} onToggleSelect={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByRole('checkbox')).toBeChecked();
  });

  it('does not render checkbox when selectionMode is false', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} selectionMode={false} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Collection badge (#823 gap-fill)
// ---------------------------------------------------------------------------

describe('BookCard – collection badge', () => {
  it('renders collection badge when in_collections > 0', () => {
    const bookWithCollections: BookResult = { ...baseBook, in_collections: 3 };

    render(
      <IntlWrapper>
        <BookCard book={bookWithCollections} />
      </IntlWrapper>
    );

    const badge = document.querySelector('.collection-badge');
    expect(badge).not.toBeNull();
  });

  it('does not render collection badge when in_collections is 0', () => {
    const bookZero: BookResult = { ...baseBook, in_collections: 0 };

    render(
      <IntlWrapper>
        <BookCard book={bookZero} />
      </IntlWrapper>
    );

    expect(document.querySelector('.collection-badge')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Thumbnail display (#827)
// ---------------------------------------------------------------------------

describe('BookCard – thumbnail', () => {
  const bookWithThumbnail: BookResult = {
    ...baseBook,
    thumbnail_url: '/thumbnails/react.jpg',
  };

  it('renders thumbnail image when thumbnail_url is present', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithThumbnail} />
      </IntlWrapper>
    );

    const img = screen.getByRole('img', { name: bookWithThumbnail.title });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', '/thumbnails/react.jpg');
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).toHaveClass('book-card-thumbnail');
  });

  it('renders placeholder when thumbnail_url is absent', () => {
    render(
      <IntlWrapper>
        <BookCard book={baseBook} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('img', { name: baseBook.title })).not.toBeInTheDocument();
    const placeholder = document.querySelector('.book-card-thumbnail--placeholder');
    expect(placeholder).not.toBeNull();
    expect(placeholder).toHaveAttribute('aria-hidden', 'true');
  });

  it('renders placeholder when thumbnail_url is null', () => {
    const bookNullThumb: BookResult = { ...baseBook, thumbnail_url: null };

    render(
      <IntlWrapper>
        <BookCard book={bookNullThumb} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('img', { name: baseBook.title })).not.toBeInTheDocument();
    expect(document.querySelector('.book-card-thumbnail--placeholder')).not.toBeNull();
  });

  it('falls back to placeholder on image load error', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithThumbnail} />
      </IntlWrapper>
    );

    const img = screen.getByRole('img', { name: bookWithThumbnail.title });
    fireEvent.error(img);

    expect(screen.queryByRole('img', { name: bookWithThumbnail.title })).not.toBeInTheDocument();
    expect(document.querySelector('.book-card-thumbnail--placeholder')).not.toBeNull();
  });

  it('uses book title as alt text for accessibility', () => {
    render(
      <IntlWrapper>
        <BookCard book={bookWithThumbnail} />
      </IntlWrapper>
    );

    const img = screen.getByRole('img', { name: 'React Patterns' });
    expect(img).toHaveAttribute('alt', 'React Patterns');
  });
});
