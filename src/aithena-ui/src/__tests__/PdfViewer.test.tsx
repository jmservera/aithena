import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import PdfViewer from '../Components/PdfViewer';
import { IntlWrapper } from './test-intl-wrapper';
import { BookResult } from '../hooks/search';

const bookWithPdf: BookResult = {
  id: 'book-1',
  title: 'Learning React',
  author: 'Jane Doe',
  document_url: '/documents/react.pdf',
};

const bookWithAbsolutePdfUrl: BookResult = {
  id: 'book-2',
  title: 'Advanced Patterns',
  author: 'John Smith',
  document_url: 'https://example.com/advanced.pdf',
};

const bookWithPage: BookResult = {
  id: 'book-3',
  title: 'React Deep Dive',
  document_url: '/documents/deep-dive.pdf',
  pages: [42, 45],
};

const bookWithoutPdf: BookResult = {
  id: 'book-4',
  title: 'No PDF Book',
};

describe('PdfViewer', () => {
  it('renders the PDF viewer dialog with the book title', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Learning React')).toBeInTheDocument();
  });

  it('renders the author name', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    expect(screen.getByText(/jane doe/i)).toBeInTheDocument();
  });

  it('closes when the close button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /close pdf viewer/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when the Escape key is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders an iframe with the document URL', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const iframe = screen.getByTitle(/learning react/i);
    expect(iframe.tagName).toBe('IFRAME');
    expect(iframe).toHaveAttribute('src', expect.stringContaining('/documents/react.pdf'));
  });

  it('appends the page anchor when pages are provided', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPage} onClose={onClose} />
      </IntlWrapper>
    );

    const iframe = screen.getByTitle(/react deep dive/i);
    expect(iframe).toHaveAttribute('src', expect.stringContaining('#page=42'));
  });

  it('handles absolute document URLs without prepending the base', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithAbsolutePdfUrl} onClose={onClose} />
      </IntlWrapper>
    );

    const iframe = screen.getByTitle(/advanced patterns/i);
    expect(iframe).toHaveAttribute('src', 'https://example.com/advanced.pdf');
  });

  it('shows an error state when no document URL is available', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithoutPdf} onClose={onClose} />
      </IntlWrapper>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/no document url available/i)).toBeInTheDocument();
  });
});
