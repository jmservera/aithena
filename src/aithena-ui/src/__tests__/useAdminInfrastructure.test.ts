import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAdminInfrastructure } from '../hooks/useAdminInfrastructure';

function mockFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

const sampleInfra = {
  services: [{ name: 'api', url: 'http://api:8080', status: 'running', type: 'service' }],
  solr_admin_url: 'http://solr:8983/solr/',
  rabbitmq_admin_url: 'http://rabbitmq:15672/',
  redis_admin_url: 'http://redis:6379/',
};

describe('useAdminInfrastructure', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('fetches infrastructure data on mount', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleInfra))
    );
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.data).toEqual(sampleInfra);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets loading true during mount fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.loading).toBe(true);
  });

  it('calls correct API endpoint', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleInfra));
    vi.stubGlobal('fetch', fetchMock);
    renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/admin/infrastructure'),
      expect.anything()
    );
  });

  it('handles API error with detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse({ detail: 'Server error' }, 500))
    );
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Server error');
    expect(result.current.data).toBeNull();
  });

  it('handles network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error throws', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue('string error'));
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Failed to load infrastructure');
  });

  it('allows manual refresh', async () => {
    const fetchMock = vi.fn().mockImplementation(() => mockFetchResponse(sampleInfra));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    const countAfterMount = fetchMock.mock.calls.length;
    await act(async () => {
      await result.current.refresh();
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(countAfterMount);
  });

  it('clears error on successful refresh after failure', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockImplementation(() => mockFetchResponse({ detail: 'Error' }, 500));
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Error');
    fetchMock.mockImplementation(() => mockFetchResponse(sampleInfra));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBeNull();
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
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.error).toBe('Request failed: 502');
  });

  it('sets loading false after successful fetch', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => mockFetchResponse(sampleInfra))
    );
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.loading).toBe(false);
  });

  it('sets loading false after error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('fail')));
    const { result } = renderHook(() => useAdminInfrastructure());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.loading).toBe(false);
  });
});
