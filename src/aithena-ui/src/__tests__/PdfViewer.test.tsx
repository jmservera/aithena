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

const bookWithInternalDocUrl: BookResult = {
  id: 'book-5',
  title: 'Internal Host Book',
  author: 'Tester',
  document_url: 'http://solr-search:8080/documents/aW50ZXJuYWwucGRm',
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

  it('renders toolbar action buttons when PDF URL is available', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    expect(screen.getByRole('button', { name: /enter fullscreen/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /download pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open in new window/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /close pdf viewer/i })).toBeInTheDocument();
  });

  it('download link has download attribute', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const downloadLink = screen.getByRole('link', { name: /download pdf/i });
    expect(downloadLink).toHaveAttribute('download');
    expect(downloadLink).toHaveAttribute('href', expect.stringContaining('/documents/react.pdf'));
  });

  it('external link opens in new window with security attributes', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const externalLink = screen.getByRole('link', { name: /open in new window/i });
    expect(externalLink).toHaveAttribute('target', '_blank');
    expect(externalLink).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('toggles fullscreen mode', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const fullscreenBtn = screen.getByRole('button', { name: /enter fullscreen/i });
    await user.click(fullscreenBtn);

    expect(screen.getByRole('button', { name: /exit fullscreen/i })).toBeInTheDocument();
  });

  it('ESC exits fullscreen first, then closes viewer', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    // Enter fullscreen
    await user.click(screen.getByRole('button', { name: /enter fullscreen/i }));
    expect(screen.getByRole('button', { name: /exit fullscreen/i })).toBeInTheDocument();

    // First ESC exits fullscreen
    await user.keyboard('{Escape}');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /enter fullscreen/i })).toBeInTheDocument();

    // Second ESC closes the viewer
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('hides download and external link buttons when no PDF URL', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithoutPdf} onClose={onClose} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('link', { name: /download pdf/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /open in new window/i })).not.toBeInTheDocument();
    // Fullscreen and close should still be present
    expect(screen.getByRole('button', { name: /enter fullscreen/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /close pdf viewer/i })).toBeInTheDocument();
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

  it('normalises internal-hostname /documents/ URLs to relative paths', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithInternalDocUrl} onClose={onClose} />
      </IntlWrapper>
    );

    const iframe = screen.getByTitle(/internal host book/i);
    expect(iframe).toHaveAttribute('src', expect.stringContaining('/documents/aW50ZXJuYWwucGRm'));
    expect(iframe.getAttribute('src')).not.toMatch(/solr-search/);
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

// ---------------------------------------------------------------------------
// Wave 1 — PDF viewer accessibility & functionality (#817)
// ---------------------------------------------------------------------------

describe('PdfViewer – accessibility', () => {
  it('dialog has role="dialog" and aria-modal="true"', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('dialog is labelled by the title element via aria-labelledby', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const dialog = screen.getByRole('dialog');
    const labelledBy = dialog.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();

    const titleEl = document.getElementById(labelledBy!);
    expect(titleEl).not.toBeNull();
    expect(titleEl!.textContent).toBe('Learning React');
  });

  it('all interactive toolbar elements have aria-labels', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const buttons = screen.getAllByRole('button');
    const links = screen.getAllByRole('link');

    for (const el of [...buttons, ...links]) {
      expect(el).toHaveAttribute('aria-label');
      expect(el.getAttribute('aria-label')!.length).toBeGreaterThan(0);
    }
  });

  it('iframe has a descriptive title attribute', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const iframe = screen.getByTitle(/learning react/i);
    expect(iframe).toBeInTheDocument();
  });
});

describe('PdfViewer – focus management', () => {
  it('moves focus to the close button on mount', () => {
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const closeBtn = screen.getByRole('button', { name: /close pdf viewer/i });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('traps forward Tab from the last focusable element to the first', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    // The iframe is the last focusable element inside the panel.
    // Focus it, then Tab should wrap to the first (fullscreen button).
    const iframe = screen.getByTitle(/learning react/i);
    (iframe as HTMLElement).focus();
    expect(document.activeElement).toBe(iframe);

    await user.tab();
    const fullscreenBtn = screen.getByRole('button', { name: /enter fullscreen/i });
    expect(document.activeElement).toBe(fullscreenBtn);
  });

  it('traps backward Shift+Tab from the first focusable element to the last', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    // Fullscreen button is the first focusable element in the panel.
    const fullscreenBtn = screen.getByRole('button', { name: /enter fullscreen/i });
    fullscreenBtn.focus();
    expect(document.activeElement).toBe(fullscreenBtn);

    // Shift+Tab from the first element should wrap to the last (iframe)
    await user.tab({ shift: true });
    const iframe = screen.getByTitle(/learning react/i);
    expect(document.activeElement).toBe(iframe);
  });
});

describe('PdfViewer – fullscreen CSS', () => {
  it('applies fullscreen CSS class when in fullscreen mode', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog.className).not.toContain('fullscreen');

    await user.click(screen.getByRole('button', { name: /enter fullscreen/i }));
    expect(dialog.className).toContain('fullscreen');
  });

  it('removes fullscreen CSS class when exiting fullscreen', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookWithPdf} onClose={onClose} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /enter fullscreen/i }));
    expect(screen.getByRole('dialog').className).toContain('fullscreen');

    await user.click(screen.getByRole('button', { name: /exit fullscreen/i }));
    expect(screen.getByRole('dialog').className).not.toContain('fullscreen');
  });
});

describe('PdfViewer – title fallback', () => {
  it('shows fallback text when title is empty string', () => {
    const bookNoTitle: BookResult = {
      id: 'book-no-title',
      title: '',
      document_url: '/documents/notitle.pdf',
    };
    const onClose = vi.fn();
    render(
      <IntlWrapper>
        <PdfViewer result={bookNoTitle} onClose={onClose} />
      </IntlWrapper>
    );

    // When title is empty, the component falls back to intl message 'pdf.document'
    const dialog = screen.getByRole('dialog');
    const titleEl = dialog.querySelector('strong');
    expect(titleEl).not.toBeNull();
    // Fallback text should not be empty
    expect(titleEl!.textContent!.length).toBeGreaterThan(0);
  });
});
