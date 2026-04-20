import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import { useAdminReindex } from '../hooks/reindex';

function mockFetch(response: object, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

describe('useAdminReindex', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts with idle state', () => {
    const { result } = renderHook(() => useAdminReindex());

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.result).toBeNull();
  });

  it('sets loading during reindex', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { result } = renderHook(() => useAdminReindex());

    act(() => {
      result.current.triggerReindex('books');
    });

    expect(result.current.loading).toBe(true);
  });

  it('returns result on success', async () => {
    const apiResult = {
      message: 'OK',
      collection: 'books',
      solr: 'cleared',
      redis_cleared: 10,
    };
    vi.stubGlobal('fetch', mockFetch(apiResult));
    const { result } = renderHook(() => useAdminReindex());

    await act(async () => {
      await result.current.triggerReindex('books');
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.result).toEqual(apiResult);
  });

  it('returns error on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
    );
    const { result } = renderHook(() => useAdminReindex());

    await act(async () => {
      await result.current.triggerReindex('books');
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Server error');
    expect(result.current.result).toBeNull();
  });

  it('handles network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network failure')));
    const { result } = renderHook(() => useAdminReindex());

    await act(async () => {
      await result.current.triggerReindex('books');
    });

    expect(result.current.error).toBe('Network failure');
  });

  it('reset clears error and result', async () => {
    const apiResult = {
      message: 'OK',
      collection: 'books',
      solr: 'cleared',
      redis_cleared: 5,
    };
    vi.stubGlobal('fetch', mockFetch(apiResult));
    const { result } = renderHook(() => useAdminReindex());

    await act(async () => {
      await result.current.triggerReindex('books');
    });
    expect(result.current.result).not.toBeNull();

    act(() => {
      result.current.reset();
    });

    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('encodes collection name in URL', async () => {
    const fetchMock = mockFetch({
      message: 'OK',
      collection: 'my books',
      solr: 'cleared',
      redis_cleared: 0,
    });
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useAdminReindex());

    await act(async () => {
      await result.current.triggerReindex('my books');
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('collection=my%20books'),
        expect.any(Object)
      );
    });
  });
});
