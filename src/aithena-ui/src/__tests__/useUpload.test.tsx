import { renderHook, waitFor } from '@testing-library/react';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import { useUpload } from '../hooks/upload';

const createMockFile = (name: string, size: number, type: string): File => {
  const blob = new Blob(['a'.repeat(size)], { type });
  return new File([blob], name, { type });
};

describe('useUpload', () => {
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

  beforeEach(() => {
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
      responseText: '',
    };

    const XMLHttpRequestMock = function (this: typeof mockXHR) {
      return mockXHR;
    };

    globalThis.XMLHttpRequest = XMLHttpRequestMock as unknown as typeof XMLHttpRequest;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with correct default state', () => {
    const { result } = renderHook(() => useUpload());

    expect(result.current.uploading).toBe(false);
    expect(result.current.progress).toBe(null);
    expect(result.current.result).toBe(null);
    expect(result.current.error).toBe(null);
  });

  it('rejects non-PDF files', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.txt', 1024, 'text/plain');

    await result.current.uploadFile(file);

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe('Only PDF files are supported');
    });

    expect(mockXHR.send).not.toHaveBeenCalled();
  });

  it('rejects files exceeding 50MB', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('large.pdf', 51 * 1024 * 1024, 'application/pdf');

    await result.current.uploadFile(file);

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe('File size exceeds 50MB limit');
    });

    expect(mockXHR.send).not.toHaveBeenCalled();
  });

  it('starts upload for valid PDF file', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    await waitFor(() => {
      expect(result.current.uploading).toBe(true);
    });

    expect(mockXHR.open).toHaveBeenCalledWith('POST', expect.stringContaining('/v1/upload'));
    expect(mockXHR.send).toHaveBeenCalled();

    // Simulate success to resolve promise
    if (mockXHR._loadHandler) {
      mockXHR.status = 200;
      mockXHR.responseText = JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'Success',
      });
      mockXHR._loadHandler();
    }

    await uploadPromise;
  });

  it('handles successful upload', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate successful response
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

    await uploadPromise;

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.result).toEqual({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'File uploaded successfully',
      });
      expect(result.current.error).toBe(null);
    });
  });

  it('handles 400 error with custom message', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate 400 error
    if (mockXHR._loadHandler) {
      mockXHR.status = 400;
      mockXHR.responseText = JSON.stringify({
        detail: 'Invalid PDF file',
      });
      mockXHR._loadHandler();
    }

    await expect(uploadPromise).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe('Invalid PDF file');
    });
  });

  it('handles 413 error (file too large)', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate 413 error
    if (mockXHR._loadHandler) {
      mockXHR.status = 413;
      mockXHR.responseText = '';
      mockXHR._loadHandler();
    }

    await expect(uploadPromise).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe(
        'File exceeds the server upload limit. Please try a smaller file.'
      );
    });
  });

  it('handles 429 error (rate limit)', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate 429 error
    if (mockXHR._loadHandler) {
      mockXHR.status = 429;
      mockXHR.responseText = '';
      mockXHR._loadHandler();
    }

    await expect(uploadPromise).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe(
        'Upload rate limit exceeded. Please try again in a minute.'
      );
    });
  });

  it('handles network error', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate network error
    if (mockXHR._errorHandler) {
      mockXHR._errorHandler();
    }

    await expect(uploadPromise).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.error).toBe('Network error. Please check your connection.');
    });
  });

  it('resets state when reset is called', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate success
    if (mockXHR._loadHandler) {
      mockXHR.status = 200;
      mockXHR.responseText = JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'Success',
      });
      mockXHR._loadHandler();
    }

    await uploadPromise;

    await waitFor(() => {
      expect(result.current.result).not.toBe(null);
    });

    // Reset (using act to wrap state updates)
    await waitFor(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.uploading).toBe(false);
      expect(result.current.progress).toBe(null);
      expect(result.current.result).toBe(null);
      expect(result.current.error).toBe(null);
    });
  });

  it('tracks upload progress', async () => {
    const { result } = renderHook(() => useUpload());
    const file = createMockFile('test.pdf', 1024, 'application/pdf');

    const uploadPromise = result.current.uploadFile(file);

    // Simulate progress event
    const uploadAddEventListener = mockXHR.upload.addEventListener;
    const calls = uploadAddEventListener.mock.calls;
    const progressCall = calls.find((call) => call[0] === 'progress');
    const progressHandler = progressCall?.[1] as ((e: ProgressEvent) => void) | undefined;

    if (progressHandler) {
      progressHandler({
        lengthComputable: true,
        loaded: 512,
        total: 1024,
      } as ProgressEvent);
    }

    await waitFor(() => {
      expect(result.current.progress).toEqual({
        loaded: 512,
        total: 1024,
        percentage: 50,
      });
    });

    // Complete upload
    if (mockXHR._loadHandler) {
      mockXHR.status = 200;
      mockXHR.responseText = JSON.stringify({
        filename: 'test.pdf',
        size: 1024,
        status: 'queued',
        message: 'Success',
      });
      mockXHR._loadHandler();
    }

    await uploadPromise;
  });
});
