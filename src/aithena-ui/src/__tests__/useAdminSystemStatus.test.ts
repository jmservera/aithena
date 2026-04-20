import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdminSystemStatus } from '../hooks/useAdminSystemStatus';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

const sampleContainers = {
  containers: [
    { name: 'api', status: 'running', type: 'service', version: '1.0.0' },
    { name: 'worker', status: 'running', type: 'service' },
  ],
  total: 2,
  healthy: 2,
  last_updated: '2024-01-01T00:00:00Z',
};

describe('useAdminSystemStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('fetches system status on mount', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers))
    );
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.data).toEqual(sampleContainers);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets loading true during fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.loading).toBe(true);
  });

  it('calls correct API endpoint', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers));
    vi.stubGlobal('fetch', fetchMock);
    renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/admin/containers'),
      expect.anything()
    );
  });

  it('handles API error with detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse({ detail: 'Server error' }, 500))
    );
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Server error');
  });

  it('handles network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error throws', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue('string error'));
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Failed to load system status');
  });

  it('auto-refreshes at 30s interval', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers));
    vi.stubGlobal('fetch', fetchMock);
    renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countAfterMount = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countAfterMount);
  });

  it('allows manual refresh', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countBefore = fetchMock.mock.calls.length;
    await act(async () => {
      await result.current.refresh();
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countBefore);
  });

  it('sets lastRefreshed after successful fetch', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers))
    );
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.lastRefreshed).toBeInstanceOf(Date);
  });

  it('isStale starts false', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleContainers))
    );
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.isStale).toBe(false);
  });

  it('recovers from error on successful refresh', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockImplementation(() => mockFetchResponse({ detail: 'Error' }, 500));
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Error');
    fetchMock.mockImplementation(() => mockFetchResponse(sampleContainers));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.data).toEqual(sampleContainers);
  });

  it('handles empty containers response', async () => {
    const emptyResponse = {
      containers: [],
      total: 0,
      healthy: 0,
      last_updated: '2024-01-01T00:00:00Z',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(emptyResponse))
    );
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.data).toEqual(emptyResponse);
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
    const { result } = renderHook(() => useAdminSystemStatus());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Request failed: 502');
  });
});
