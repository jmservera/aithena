import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdmin } from '../hooks/admin';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

const sampleDocuments = {
  total: 3,
  queued: 1,
  processed: 1,
  failed: 1,
  documents: [
    { id: 'doc-1', status: 'queued', path: '/books/a.pdf' },
    { id: 'doc-2', status: 'processed', path: '/books/b.pdf', page_count: 10 },
    { id: 'doc-3', status: 'failed', path: '/books/c.pdf', error: 'Parse error' },
  ],
};

describe('useAdmin', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('starts with null data and no loading', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdmin());
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('loads document data on refresh', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => mockFetchResponse(sampleDocuments)));
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.data).toEqual(sampleDocuments);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets loading true during refresh', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdmin());
    act(() => {
      result.current.refresh();
    });
    expect(result.current.loading).toBe(true);
  });

  it('sets error on API failure with detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => mockFetchResponse({ detail: 'Service unavailable' }, 503)));
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Service unavailable');
    expect(result.current.data).toBeNull();
  });

  it('sets error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error throws gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue('string error'));
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Failed to load queue state');
  });

  it('requeueDocument calls POST and refreshes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleDocuments));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.requeueDocument('doc-3');
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain('/v1/admin/documents/doc-3/requeue');
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'POST' }));
  });

  it('requeueAllFailed calls POST and refreshes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleDocuments));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.requeueAllFailed();
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/v1/admin/documents/requeue-failed');
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'POST' }));
  });

  it('clearProcessed calls DELETE and refreshes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleDocuments));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.clearProcessed();
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/v1/admin/documents/processed');
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'DELETE' }));
  });

  it('deleteDocument calls DELETE with correct id', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleDocuments));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.deleteDocument('doc-2');
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/v1/admin/documents/doc-2');
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'DELETE' }));
  });

  it('clears error on successful refresh after failure', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockImplementationOnce(() => mockFetchResponse({ detail: 'Error' }, 500));
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Error');
    fetchMock.mockImplementationOnce(() => mockFetchResponse(sampleDocuments));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBeNull();
  });

  it('handles API error with no detail field', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({ ok: false, status: 500, json: async () => ({ message: 'no detail' }) })
      )
    );
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Request failed: 500');
  });

  it('handles API error when json parsing fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: false,
          status: 502,
          json: async () => {
            throw new Error('bad json');
          },
        })
      )
    );
    const { result } = renderHook(() => useAdmin());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Request failed: 502');
  });
});
