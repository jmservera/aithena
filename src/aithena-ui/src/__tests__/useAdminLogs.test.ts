import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdminLogs } from '../hooks/useAdminLogs';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

function mockLogsFetchResponse(text: string, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({}),
    text: async () => text,
  });
}

const sampleContainers = {
  containers: [
    { name: 'api', status: 'running' },
    { name: 'worker', status: 'running' },
  ],
};

const sampleLogLines = 'line1\nline2\nline3';

function routeFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes('/v1/admin/logs/')) {
      return overrides.logs !== undefined ? overrides.logs : mockLogsFetchResponse(sampleLogLines);
    }
    if (url.includes('/v1/admin/containers')) {
      return overrides.containers !== undefined
        ? overrides.containers
        : mockFetchResponse(sampleContainers);
    }
    return mockFetchResponse({});
  });
}

describe('useAdminLogs', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('has initial default state', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminLogs());
    expect(result.current.services).toEqual([]);
    expect(result.current.selectedService).toBe('');
    expect(result.current.tailLines).toBe(100);
    expect(result.current.logLines).toEqual([]);
    expect(result.current.autoRefresh).toBe(false);
    expect(result.current.refreshInterval).toBe(30_000);
    expect(result.current.searchFilter).toBe('');
  });

  it('fetches services on mount', async () => {
    vi.stubGlobal('fetch', routeFetch());
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.services).toEqual(sampleContainers.containers);
    expect(result.current.servicesLoading).toBe(false);
    expect(result.current.servicesError).toBeNull();
  });

  it('handles services fetch error', async () => {
    vi.stubGlobal(
      'fetch',
      routeFetch({ containers: mockFetchResponse({ detail: 'Services error' }, 500) })
    );
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.servicesError).toBe('Services error');
    expect(result.current.services).toEqual([]);
  });

  it('fetches logs when service is selected', async () => {
    vi.stubGlobal('fetch', routeFetch());
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.logLines).toEqual(['line1', 'line2', 'line3']);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('uses correct tail parameter in URL', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const logCall = fetchMock.mock.calls.find((c) => c[0].includes('/v1/admin/logs/'));
    expect(logCall?.[0]).toContain('tail=100');
  });

  it('handles logs fetch error', async () => {
    vi.stubGlobal('fetch', routeFetch({ logs: mockFetchResponse({ detail: 'Logs error' }, 500) }));
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Logs error');
    expect(result.current.logLines).toEqual([]);
  });

  it('refresh does nothing when no service selected', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countBefore = fetchMock.mock.calls.length;
    await act(async () => {
      await result.current.refresh();
    });
    // Only services fetch should have happened, no log fetch
    expect(fetchMock.mock.calls.length).toBe(countBefore);
  });

  it('auto-refreshes logs when enabled with selected service', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setAutoRefresh(true);
    });
    const countBefore = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countBefore);
  });

  it('stops auto-refresh when disabled', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setAutoRefresh(true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setAutoRefresh(false);
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

  it('URL-encodes service name', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('my service');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const logCall = fetchMock.mock.calls.find((c) => c[0].includes('/v1/admin/logs/'));
    expect(logCall?.[0]).toContain('my%20service');
  });

  it('sets search filter', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminLogs());
    act(() => {
      result.current.setSearchFilter('error');
    });
    expect(result.current.searchFilter).toBe('error');
  });

  it('sets refresh interval', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminLogs());
    act(() => {
      result.current.setRefreshInterval(60_000);
    });
    expect(result.current.refreshInterval).toBe(60_000);
  });

  it('changes tail lines and re-fetches logs', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setTailLines(200);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.tailLines).toBe(200);
    const logCalls = fetchMock.mock.calls.filter((c) => c[0].includes('/v1/admin/logs/'));
    const lastLogCall = logCalls[logCalls.length - 1];
    expect(lastLogCall?.[0]).toContain('tail=200');
  });

  it('handles network error on logs fetch', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/v1/admin/logs/')) {
        return Promise.reject(new Error('Network error'));
      }
      if (url.includes('/v1/admin/containers')) {
        return mockFetchResponse(sampleContainers);
      }
      return mockFetchResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    act(() => {
      result.current.setSelectedService('api');
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error throws on services fetch', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/v1/admin/containers')) {
        return Promise.reject('string error');
      }
      return mockFetchResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminLogs());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.servicesError).toBe('Failed to load services');
  });
});
