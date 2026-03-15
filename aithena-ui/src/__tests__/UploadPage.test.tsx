import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import UploadPage from '../pages/UploadPage';

const createMockFile = (name: string, size: number, type: string): File => {
  const blob = new Blob(['a'.repeat(size)], { type });
  return new File([blob], name, { type });
};

describe('UploadPage', () => {
  let mockXHR: {
    open: ReturnType<typeof vi.fn>;
    send: ReturnType<typeof vi.fn>;
    setRequestHeader: ReturnType<typeof vi.fn>;
    upload: {
      addEventListener: ReturnType<typeof vi.fn>;
    };
    addEventListener: ReturnType<typeof vi.fn>;
    status: number;
    responseText: string;
    _loadHandler?: () => void;
    _errorHandler?: () => void;
    _abortHandler?: () => void;
  };
  let xhrInstances: typeof mockXHR[] = [];

  beforeEach(() => {
    xhrInstances = [];

    mockXHR = {
      open: vi.fn(),
      send: vi.fn(),
      setRequestHeader: vi.fn(),
      upload: {
        addEventListener: vi.fn(),
      },
      addEventListener: vi.fn((event: string, handler: () => void) => {
        if (event === 'load') {
          mockXHR._loadHandler = handler;
        } else if (event === 'error') {
          mockXHR._errorHandler = handler;
        } else if (event === 'abort') {
          mockXHR._abortHandler = handler;
        }
      }),
      status: 200,
      responseText: JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'File uploaded successfully and queued for indexing',
      }),
    };

    const XMLHttpRequestMock = function (this: typeof mockXHR) {
      xhrInstances.push(mockXHR);
      return mockXHR;
    };

    globalThis.XMLHttpRequest = XMLHttpRequestMock as unknown as typeof XMLHttpRequest;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders upload dropzone', () => {
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Upload PDF')).toBeInTheDocument();
    expect(screen.getByText(/Add a new book to the library/)).toBeInTheDocument();
    expect(screen.getByText(/Drag and drop a PDF file here/)).toBeInTheDocument();
    expect(screen.getByText(/Maximum file size: 50MB/)).toBeInTheDocument();
  });

  it('allows file selection via file input', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const browseButton = screen.getByRole('button', { name: /browse/i });
    await user.click(browseButton);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
  });

  it('uploads file successfully and shows success message', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Wait for upload to start and XHR to be created, then simulate success
    await waitFor(() => {
      if (mockXHR._loadHandler) {
        mockXHR.status = 200;
        mockXHR.responseText = JSON.stringify({
          filename: 'test.pdf',
          size: 1024,
          status: 'queued',
          message: 'File uploaded successfully and queued for indexing',
        });
        mockXHR._loadHandler();
      }
      expect(screen.getByText('Upload Successful')).toBeInTheDocument();
    });

    expect(
      screen.getByText('File uploaded successfully and queued for indexing')
    ).toBeInTheDocument();
    expect(screen.getByText(/Filename:/)).toBeInTheDocument();
    expect(screen.getByText('test.pdf')).toBeInTheDocument();
  });

  it('shows error for non-PDF files', async () => {
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.txt', 1024, 'text/plain');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    // Manually set files and trigger change event
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fileInput.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    expect(screen.getByText('Only PDF files are supported')).toBeInTheDocument();
  });

  it('shows error for files exceeding size limit', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('large.pdf', 51 * 1024 * 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    await waitFor(() => {
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
      expect(screen.getByText('File size exceeds 50MB limit')).toBeInTheDocument();
    });
  });

  it('handles server error response', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate server error within waitFor
    await waitFor(() => {
      if (mockXHR._loadHandler) {
        mockXHR.status = 500;
        mockXHR.responseText = JSON.stringify({
          detail: 'Internal server error',
        });
        mockXHR._loadHandler();
      }
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    expect(screen.getByText('Internal server error')).toBeInTheDocument();
  });

  it('handles rate limit error (429)', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate rate limit within waitFor
    await waitFor(() => {
      if (mockXHR._loadHandler) {
        mockXHR.status = 429;
        mockXHR.responseText = '';
        mockXHR._loadHandler();
      }
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    expect(
      screen.getByText('Upload rate limit exceeded. Please try again in a minute.')
    ).toBeInTheDocument();
  });

  it('handles network error', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate network error within waitFor
    await waitFor(() => {
      if (mockXHR._errorHandler) {
        mockXHR._errorHandler();
      }
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error. Please check your connection.')).toBeInTheDocument();
  });

  it('allows retry after error', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate error within waitFor
    await waitFor(() => {
      if (mockXHR._loadHandler) {
        mockXHR.status = 500;
        mockXHR.responseText = '';
        mockXHR._loadHandler();
      }
      expect(screen.getByText('Upload Failed')).toBeInTheDocument();
    });

    // Click try again
    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    await user.click(tryAgainButton);

    // Should show dropzone again
    expect(screen.getByText(/Drag and drop a PDF file here/)).toBeInTheDocument();
  });

  it('allows uploading another file after success', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate success for uploading another file
    if (mockXHR._loadHandler) {
      mockXHR.status = 200;
      mockXHR.responseText = JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'File uploaded successfully',
      });
      mockXHR._loadHandler();
    }

    await waitFor(() => {
      expect(screen.getByText('Upload Successful')).toBeInTheDocument();
    });

    // Click upload another
    const uploadAnotherButton = screen.getByRole('button', { name: /upload another/i });
    await user.click(uploadAnotherButton);

    // Should show dropzone again
    expect(screen.getByText(/Drag and drop a PDF file here/)).toBeInTheDocument();
  });

  it('provides link back to search after success', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    );

    const file = createMockFile('test.pdf', 1024, 'application/pdf');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    // Simulate success for link to search
    if (mockXHR._loadHandler) {
      mockXHR.status = 200;
      mockXHR.responseText = JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'File uploaded successfully',
      });
      mockXHR._loadHandler();
    }

    await waitFor(() => {
      expect(screen.getByText('Upload Successful')).toBeInTheDocument();
    });

    const backToSearchLink = screen.getByRole('link', { name: /back to search/i });
    expect(backToSearchLink).toBeInTheDocument();
    expect(backToSearchLink).toHaveAttribute('href', '/search');
  });
});
