import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdminIndexingStatus } from '../hooks/useAdminIndexingStatus';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

const sampleData = {
  summary: {
    total: 10,
    queued: 2,
    processing: 1,
    processed: 6,
    failed: 1,
    total_pages: 100,
    total_chunks: 500,
  },
  documents: [
    {
      id: 'd1',
      status: 'queued',
      path: '/a.pdf',
      text_indexed: false,
      embedding_indexed: false,
      page_count: 5,
      chunk_count: 20,
    },
  ],
};

describe('useAdminIndexingStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('has initial state with default values', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminIndexingStatus());
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.autoRefresh).toBe(false);
    expect(result.current.statusFilter).toBe('all');
    expect(result.current.page).toBe(1);
  });

  it('fetches indexing status on manual refresh', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleData))
    );
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.data).toEqual(sampleData);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets loading true during fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.refresh();
    });
    expect(result.current.loading).toBe(true);
  });

  it('handles API error with detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse({ detail: 'Server error' }, 500))
    );
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Server error');
  });

  it('handles API error without detail field', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse({ message: 'nope' }, 500))
    );
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Request failed: 500');
  });

  it('handles network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error throws', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue('string error'));
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Failed to load indexing status');
  });

  it('clears error on successful refresh after failure', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockImplementationOnce(() => mockFetchResponse({ detail: 'Error' }, 500));
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Error');
    fetchMock.mockImplementationOnce(() => mockFetchResponse(sampleData));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBeNull();
  });

  it('auto-refreshes when enabled', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleData));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.setAutoRefresh(true);
    });
    const countBefore = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countBefore);
  });

  it('stops auto-refresh when disabled', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleData));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.setAutoRefresh(true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    act(() => {
      result.current.setAutoRefresh(false);
    });
    const countAfter = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(fetchMock.mock.calls.length).toBe(countAfter);
  });

  it('calls correct API endpoint', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleData));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/admin/indexing-status'),
      expect.anything()
    );
  });

  it('resets page to 1 when changing status filter', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.setPage(3);
    });
    expect(result.current.page).toBe(3);
    act(() => {
      result.current.setStatusFilter('failed');
    });
    expect(result.current.page).toBe(1);
    expect(result.current.statusFilter).toBe('failed');
  });

  it('allows changing page number', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.setPage(5);
    });
    expect(result.current.page).toBe(5);
  });

  it('handles different status filters', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminIndexingStatus());
    act(() => {
      result.current.setStatusFilter('processing');
    });
    expect(result.current.statusFilter).toBe('processing');
  });

  it('handles JSON parse error in error response', async () => {
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
    const { result } = renderHook(() => useAdminIndexingStatus());
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe('Request failed: 502');
  });
});
