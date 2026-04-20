import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdminDashboard } from '../hooks/useAdminDashboard';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

const sampleDocs = { total: 5, queued: 1, processed: 3, failed: 1 };
const sampleQueue = {
  queue_name: 'indexing',
  messages_ready: 2,
  messages_unacknowledged: 0,
  messages_total: 2,
  consumers: 1,
  status: 'running',
};
const sampleInfra = {
  containers: [{ name: 'api', status: 'running', type: 'service' }],
  total: 1,
  healthy: 1,
  last_updated: '2024-01-01T00:00:00Z',
};

function routeFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/documents')) {
      return overrides.documents !== undefined
        ? overrides.documents
        : mockFetchResponse(sampleDocs);
    }
    if (url.includes('/v1/admin/queue-status')) {
      return overrides.queue !== undefined ? overrides.queue : mockFetchResponse(sampleQueue);
    }
    if (url.includes('/v1/admin/containers')) {
      return overrides.infrastructure !== undefined
        ? overrides.infrastructure
        : mockFetchResponse(sampleInfra);
    }
    return mockFetchResponse({});
  });
}

describe('useAdminDashboard', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('has initial state with autoRefresh true', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminDashboard());
    expect(result.current.autoRefresh).toBe(true);
    expect(result.current.documents).toBeNull();
    expect(result.current.queue).toBeNull();
    expect(result.current.infrastructure).toBeNull();
  });

  it('fetches all three APIs on mount', async () => {
    vi.stubGlobal('fetch', routeFetch());
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.documents).toEqual(sampleDocs);
    expect(result.current.queue).toEqual(sampleQueue);
    expect(result.current.infrastructure).toEqual(sampleInfra);
    expect(result.current.loading).toBe(false);
  });

  it('handles documents API error individually', async () => {
    vi.stubGlobal(
      'fetch',
      routeFetch({ documents: mockFetchResponse({ detail: 'Docs error' }, 500) })
    );
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.documents).toBe('Docs error');
    expect(result.current.queue).toEqual(sampleQueue);
    expect(result.current.infrastructure).toEqual(sampleInfra);
  });

  it('handles queue API error individually', async () => {
    vi.stubGlobal(
      'fetch',
      routeFetch({ queue: mockFetchResponse({ detail: 'Queue error' }, 503) })
    );
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.queue).toBe('Queue error');
    expect(result.current.documents).toEqual(sampleDocs);
  });

  it('handles infrastructure API error individually', async () => {
    vi.stubGlobal(
      'fetch',
      routeFetch({ infrastructure: mockFetchResponse({ detail: 'Infra error' }, 502) })
    );
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.infrastructure).toBe('Infra error');
    expect(result.current.documents).toEqual(sampleDocs);
  });

  it('toggles autoRefresh', async () => {
    vi.stubGlobal('fetch', routeFetch());
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.autoRefresh).toBe(true);
    act(() => {
      result.current.toggleAutoRefresh();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.autoRefresh).toBe(false);
  });

  it('auto-refreshes at 30s interval when enabled', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const initialCount = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCount);
  });

  it('stops auto-refresh when disabled', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.toggleAutoRefresh();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countAfterDisable = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchMock.mock.calls.length).toBe(countAfterDisable);
  });

  it('allows manual refresh', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countBefore = fetchMock.mock.calls.length;
    await act(async () => {
      await result.current.refresh();
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countBefore);
  });

  it('handles all APIs failing', async () => {
    vi.stubGlobal(
      'fetch',
      routeFetch({
        documents: mockFetchResponse({ detail: 'err1' }, 500),
        queue: mockFetchResponse({ detail: 'err2' }, 500),
        infrastructure: mockFetchResponse({ detail: 'err3' }, 500),
      })
    );
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.documents).toBe('err1');
    expect(result.current.errors.queue).toBe('err2');
    expect(result.current.errors.infrastructure).toBe('err3');
  });

  it('sets lastRefreshed after successful fetch', async () => {
    vi.stubGlobal('fetch', routeFetch());
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.lastRefreshed).toBeInstanceOf(Date);
  });

  it('handles non-Error exceptions gracefully', async () => {
    vi.stubGlobal('fetch', routeFetch({ documents: Promise.reject('string error') }));
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.documents).toBe('Failed to load documents');
  });

  it('handles API error without detail field', async () => {
    vi.stubGlobal('fetch', routeFetch({ queue: mockFetchResponse({ message: 'nope' }, 500) }));
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.errors.queue).toBe('Request failed: 500');
  });

  it('maintains loading state during fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminDashboard());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.loading).toBe(true);
  });
});
