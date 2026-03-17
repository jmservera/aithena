import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

import {
  parseSearchParams,
  stateToParams,
  useSearchState,
  DEFAULTS,
} from '../hooks/useSearchState';
import type { SearchState } from '../hooks/search';

// -- Unit tests: parseSearchParams --

describe('parseSearchParams', () => {
  it('returns defaults for empty params', () => {
    const result = parseSearchParams(new URLSearchParams());
    expect(result).toEqual(DEFAULTS);
  });

  it('parses a full set of params', () => {
    const params = new URLSearchParams({
      q: 'machine learning',
      page: '3',
      sort: 'year_i desc',
      mode: 'semantic',
      limit: '20',
      filter_author: 'Jane Doe',
      filter_category: 'Science',
      filter_language: 'English',
      filter_year: '2023',
    });

    expect(parseSearchParams(params)).toEqual({
      query: 'machine learning',
      page: 3,
      sort: 'year_i desc',
      mode: 'semantic',
      limit: 20,
      filters: {
        author: 'Jane Doe',
        category: 'Science',
        language: 'English',
        year: '2023',
      },
    });
  });

  it('falls back to defaults for invalid page', () => {
    const params = new URLSearchParams({ page: 'abc' });
    expect(parseSearchParams(params).page).toBe(1);
  });

  it('falls back to defaults for negative page', () => {
    const params = new URLSearchParams({ page: '-5' });
    expect(parseSearchParams(params).page).toBe(1);
  });

  it('floors fractional page numbers', () => {
    const params = new URLSearchParams({ page: '2.7' });
    expect(parseSearchParams(params).page).toBe(2);
  });

  it('falls back to default sort for invalid sort value', () => {
    const params = new URLSearchParams({ sort: 'invalid' });
    expect(parseSearchParams(params).sort).toBe('score desc');
  });

  it('falls back to default mode for invalid mode', () => {
    const params = new URLSearchParams({ mode: 'turbo' });
    expect(parseSearchParams(params).mode).toBe('keyword');
  });

  it('falls back to default limit for invalid limit', () => {
    const params = new URLSearchParams({ limit: '15' });
    expect(parseSearchParams(params).limit).toBe(10);
  });

  it('ignores unknown filter_ prefixed params', () => {
    const params = new URLSearchParams({ filter_unknown: 'value' });
    expect(parseSearchParams(params).filters).toEqual({});
  });

  it('decodes URL-encoded values from a query string', () => {
    // Construct from a raw query string so %-encoding is decoded by URLSearchParams.
    const params = new URLSearchParams('q=hello+world&filter_author=O%27Brien');
    const result = parseSearchParams(params);
    expect(result.query).toBe('hello world');
    expect(result.filters.author).toBe("O'Brien");
  });
});

// -- Unit tests: stateToParams --

describe('stateToParams', () => {
  it('returns empty params for default state', () => {
    const params = stateToParams(DEFAULTS);
    expect(params.toString()).toBe('');
  });

  it('only includes non-default values', () => {
    const state: SearchState = {
      ...DEFAULTS,
      query: 'react',
    };
    const params = stateToParams(state);
    expect(params.get('q')).toBe('react');
    expect(params.has('page')).toBe(false);
    expect(params.has('sort')).toBe(false);
    expect(params.has('mode')).toBe(false);
    expect(params.has('limit')).toBe(false);
  });

  it('includes page only when > 1', () => {
    const state: SearchState = { ...DEFAULTS, query: 'react', page: 3 };
    const params = stateToParams(state);
    expect(params.get('page')).toBe('3');
  });

  it('serialises filters with filter_ prefix', () => {
    const state: SearchState = {
      ...DEFAULTS,
      query: 'react',
      filters: { author: 'Jane', year: '2023' },
    };
    const params = stateToParams(state);
    expect(params.get('filter_author')).toBe('Jane');
    expect(params.get('filter_year')).toBe('2023');
    expect(params.has('filter_category')).toBe(false);
  });

  it('includes sort only when non-default', () => {
    const state: SearchState = { ...DEFAULTS, sort: 'year_i desc' };
    const params = stateToParams(state);
    expect(params.get('sort')).toBe('year_i desc');
  });

  it('includes mode only when non-default', () => {
    const state: SearchState = { ...DEFAULTS, mode: 'hybrid' };
    const params = stateToParams(state);
    expect(params.get('mode')).toBe('hybrid');
  });

  it('includes limit only when non-default', () => {
    const state: SearchState = { ...DEFAULTS, limit: 50 };
    const params = stateToParams(state);
    expect(params.get('limit')).toBe('50');
  });
});

// -- Round-trip --

describe('round-trip: stateToParams -> parseSearchParams', () => {
  it('preserves a fully populated state', () => {
    const state: SearchState = {
      query: 'deep learning',
      page: 5,
      sort: 'title_s asc',
      mode: 'hybrid',
      limit: 50,
      filters: {
        author: 'Ada Lovelace',
        category: 'AI',
        language: 'English',
        year: '2024',
      },
    };
    expect(parseSearchParams(stateToParams(state))).toEqual(state);
  });

  it('preserves default state (empty URL)', () => {
    expect(parseSearchParams(stateToParams(DEFAULTS))).toEqual(DEFAULTS);
  });
});

// -- Hook integration tests --

function createWrapper(initialEntries: string[] = ['/search']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
  };
}

describe('useSearchState hook', () => {
  it('returns defaults when URL has no search params', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('initialises state from URL params (deep link)', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=react&page=2&mode=semantic']),
    });

    const state = result.current[0];
    expect(state.query).toBe('react');
    expect(state.page).toBe(2);
    expect(state.mode).toBe('semantic');
  });

  it('initialises filters from URL params', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=test&filter_author=Doe&filter_year=2023']),
    });

    expect(result.current[0].filters).toEqual({ author: 'Doe', year: '2023' });
  });

  it('updates state and URL via setter with value', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, query: 'typescript' });
    });

    expect(result.current[0].query).toBe('typescript');
  });

  it('updates state and URL via setter with updater function', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=react']),
    });

    act(() => {
      result.current[1]((prev) => ({ ...prev, page: 3 }));
    });

    expect(result.current[0].query).toBe('react');
    expect(result.current[0].page).toBe(3);
  });

  it('clears params when returning to defaults', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=react&page=5']),
    });

    act(() => {
      result.current[1](DEFAULTS);
    });

    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('handles special characters in query', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, query: 'C++ & algorithms' });
    });

    expect(result.current[0].query).toBe('C++ & algorithms');
  });

  it('handles special characters in filter values', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({
        ...DEFAULTS,
        query: 'test',
        filters: { author: "O'Brien & Associates" },
      });
    });

    expect(result.current[0].filters.author).toBe("O'Brien & Associates");
  });

  it('sanitises invalid URL params to defaults', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=test&page=abc&sort=bad&mode=nope&limit=999']),
    });

    const state = result.current[0];
    expect(state.query).toBe('test');
    expect(state.page).toBe(1);
    expect(state.sort).toBe('score desc');
    expect(state.mode).toBe('keyword');
    expect(state.limit).toBe(10);
  });
});
