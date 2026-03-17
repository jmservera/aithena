/**
 * Integration tests for useSearchState — URL state persistence.
 *
 * Tests the full cycle: URL → state → setter → URL, including edge cases,
 * filter combinations, and state restoration on simulated page reload.
 */
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
import type { SearchState, SearchFilters } from '../hooks/search';

// -- Helper --

function createWrapper(initialEntries: string[] = ['/search']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
  };
}

// ── URL state restoration (simulated page reload) ──

describe('URL state restoration', () => {
  it('restores full search state from URL on init', () => {
    const url =
      '/search?q=machine+learning&page=5&sort=year_i+desc&mode=semantic&limit=20&filter_author=Turing&filter_category=AI';
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper([url]),
    });

    const state = result.current[0];
    expect(state.query).toBe('machine learning');
    expect(state.page).toBe(5);
    expect(state.sort).toBe('year_i desc');
    expect(state.mode).toBe('semantic');
    expect(state.limit).toBe(20);
    expect(state.filters.author).toBe('Turing');
    expect(state.filters.category).toBe('AI');
  });

  it('restores only query when other params are defaults', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=typescript']),
    });

    const state = result.current[0];
    expect(state.query).toBe('typescript');
    expect(state.page).toBe(1);
    expect(state.sort).toBe(DEFAULTS.sort);
    expect(state.mode).toBe(DEFAULTS.mode);
    expect(state.limit).toBe(DEFAULTS.limit);
    expect(state.filters).toEqual({});
  });

  it('restores all four filter types', () => {
    const url =
      '/search?q=test&filter_author=Doe&filter_category=Fiction&filter_language=Spanish&filter_year=2020';
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper([url]),
    });

    expect(result.current[0].filters).toEqual({
      author: 'Doe',
      category: 'Fiction',
      language: 'Spanish',
      year: '2020',
    });
  });

  it('ignores unknown URL parameters gracefully', () => {
    const url = '/search?q=test&unknown=yes&debug=true&filter_unknown=nope';
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper([url]),
    });

    const state = result.current[0];
    expect(state.query).toBe('test');
    expect(state.filters).toEqual({});
  });
});

// ── Filter persistence via setter ──

describe('filter persistence', () => {
  it('sets a single filter and reflects in state', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({
        ...DEFAULTS,
        query: 'react',
        filters: { author: 'Doe' },
      });
    });

    expect(result.current[0].filters.author).toBe('Doe');
    expect(result.current[0].query).toBe('react');
  });

  it('sets multiple filters at once', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    const filters: SearchFilters = {
      author: 'Smith',
      category: 'Science',
      language: 'English',
      year: '2024',
    };

    act(() => {
      result.current[1]({ ...DEFAULTS, query: 'biology', filters });
    });

    expect(result.current[0].filters).toEqual(filters);
  });

  it('clears filters by setting empty object', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=test&filter_author=Doe&filter_year=2023']),
    });

    expect(result.current[0].filters.author).toBe('Doe');

    act(() => {
      result.current[1]((prev) => ({ ...prev, filters: {} }));
    });

    expect(result.current[0].filters).toEqual({});
  });

  it('replaces one filter while keeping others', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({
        ...DEFAULTS,
        query: 'test',
        filters: { author: 'A', category: 'B' },
      });
    });

    act(() => {
      result.current[1]((prev) => ({
        ...prev,
        filters: { ...prev.filters, author: 'C' },
      }));
    });

    expect(result.current[0].filters.author).toBe('C');
    expect(result.current[0].filters.category).toBe('B');
  });
});

// ── Sort order persistence ──

describe('sort order persistence', () => {
  it('sets and restores year_i desc sort', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, sort: 'year_i desc' });
    });

    expect(result.current[0].sort).toBe('year_i desc');
  });

  it('restores sort from URL', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?sort=title_s+asc']),
    });

    expect(result.current[0].sort).toBe('title_s asc');
  });

  it('falls back to default for invalid sort in URL', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?sort=invalid_sort']),
    });

    expect(result.current[0].sort).toBe(DEFAULTS.sort);
  });

  for (const sort of ['score desc', 'year_i desc', 'year_i asc', 'title_s asc', 'author_s asc']) {
    it(`round-trips sort value: "${sort}"`, () => {
      const state: SearchState = { ...DEFAULTS, sort };
      const restored = parseSearchParams(stateToParams(state));
      expect(restored.sort).toBe(sort);
    });
  }
});

// ── Pagination persistence ──

describe('pagination persistence', () => {
  it('sets page via updater function', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=test']),
    });

    act(() => {
      result.current[1]((prev) => ({ ...prev, page: 7 }));
    });

    expect(result.current[0].page).toBe(7);
  });

  it('restores page from URL', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=test&page=4']),
    });

    expect(result.current[0].page).toBe(4);
  });

  it('resets page to 1 when updating query', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?q=old&page=5']),
    });

    act(() => {
      result.current[1]((prev) => ({ ...prev, query: 'new', page: 1 }));
    });

    expect(result.current[0].page).toBe(1);
    expect(result.current[0].query).toBe('new');
  });

  it('omits page=1 from URL params (clean URL)', () => {
    const state: SearchState = { ...DEFAULTS, query: 'test', page: 1 };
    const params = stateToParams(state);
    expect(params.has('page')).toBe(false);
  });

  it('includes page > 1 in URL params', () => {
    const state: SearchState = { ...DEFAULTS, query: 'test', page: 3 };
    const params = stateToParams(state);
    expect(params.get('page')).toBe('3');
  });
});

// ── Search mode persistence ──

describe('search mode persistence', () => {
  it('sets and reads semantic mode', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, mode: 'semantic' });
    });

    expect(result.current[0].mode).toBe('semantic');
  });

  it('sets and reads hybrid mode', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, mode: 'hybrid' });
    });

    expect(result.current[0].mode).toBe('hybrid');
  });

  it('restores mode from URL', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?mode=hybrid']),
    });

    expect(result.current[0].mode).toBe('hybrid');
  });

  it('falls back to keyword for invalid mode', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?mode=turbo']),
    });

    expect(result.current[0].mode).toBe('keyword');
  });

  for (const mode of ['keyword', 'semantic', 'hybrid'] as const) {
    it(`round-trips mode: "${mode}"`, () => {
      const state: SearchState = { ...DEFAULTS, mode };
      const restored = parseSearchParams(stateToParams(state));
      expect(restored.mode).toBe(mode);
    });
  }
});

// ── Limit persistence ──

describe('limit persistence', () => {
  it('sets limit to 20', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, limit: 20 });
    });

    expect(result.current[0].limit).toBe(20);
  });

  it('sets limit to 50', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({ ...DEFAULTS, limit: 50 });
    });

    expect(result.current[0].limit).toBe(50);
  });

  it('falls back to default for non-standard limit', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?limit=25']),
    });

    expect(result.current[0].limit).toBe(DEFAULTS.limit);
  });

  it('falls back to default for zero limit', () => {
    const params = new URLSearchParams({ limit: '0' });
    expect(parseSearchParams(params).limit).toBe(DEFAULTS.limit);
  });

  it('falls back to default for negative limit', () => {
    const params = new URLSearchParams({ limit: '-10' });
    expect(parseSearchParams(params).limit).toBe(DEFAULTS.limit);
  });
});

// ── Edge cases: empty / invalid params ──

describe('edge cases', () => {
  it('handles completely empty URL', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search']),
    });

    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('handles URL with only unknown params', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(['/search?foo=bar&baz=qux']),
    });

    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('handles all params invalid simultaneously', () => {
    const url = '/search?page=-1&sort=nope&mode=turbo&limit=999';
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper([url]),
    });

    const state = result.current[0];
    expect(state.page).toBe(1);
    expect(state.sort).toBe(DEFAULTS.sort);
    expect(state.mode).toBe(DEFAULTS.mode);
    expect(state.limit).toBe(DEFAULTS.limit);
  });

  it('preserves special characters in query through setter round-trip', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    const specialQuery = 'C++ programming & data structures (2nd ed.)';
    act(() => {
      result.current[1]({ ...DEFAULTS, query: specialQuery });
    });

    expect(result.current[0].query).toBe(specialQuery);
  });

  it('preserves unicode characters in filters', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current[1]({
        ...DEFAULTS,
        query: 'test',
        filters: { author: 'José García' },
      });
    });

    expect(result.current[0].filters.author).toBe('José García');
  });

  it('handles page=0 as invalid', () => {
    const params = new URLSearchParams({ page: '0' });
    expect(parseSearchParams(params).page).toBe(1);
  });

  it('handles page=Infinity as invalid', () => {
    const params = new URLSearchParams({ page: 'Infinity' });
    // Infinity is finite? No — Number.isFinite(Infinity) === false
    expect(parseSearchParams(params).page).toBe(1);
  });

  it('handles page=NaN as invalid', () => {
    const params = new URLSearchParams({ page: 'NaN' });
    expect(parseSearchParams(params).page).toBe(1);
  });

  it('handles empty string values for filters', () => {
    const params = new URLSearchParams({ filter_author: '' });
    expect(parseSearchParams(params).filters).toEqual({});
  });
});

// ── Multi-step state changes ──

describe('multi-step state changes', () => {
  it('applies sequential updates correctly', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper(),
    });

    // Step 1: set query
    act(() => {
      result.current[1]({ ...DEFAULTS, query: 'python' });
    });
    expect(result.current[0].query).toBe('python');

    // Step 2: add filter
    act(() => {
      result.current[1]((prev) => ({
        ...prev,
        filters: { author: 'Guido' },
      }));
    });
    expect(result.current[0].query).toBe('python');
    expect(result.current[0].filters.author).toBe('Guido');

    // Step 3: change page
    act(() => {
      result.current[1]((prev) => ({ ...prev, page: 3 }));
    });
    expect(result.current[0].query).toBe('python');
    expect(result.current[0].filters.author).toBe('Guido');
    expect(result.current[0].page).toBe(3);

    // Step 4: change sort
    act(() => {
      result.current[1]((prev) => ({ ...prev, sort: 'year_i asc' }));
    });
    expect(result.current[0].sort).toBe('year_i asc');
    expect(result.current[0].query).toBe('python');
  });

  it('reset to defaults clears everything', () => {
    const { result } = renderHook(() => useSearchState(), {
      wrapper: createWrapper([
        '/search?q=test&page=5&sort=year_i+desc&mode=semantic&limit=50&filter_author=Smith',
      ]),
    });

    // Verify loaded state
    expect(result.current[0].query).toBe('test');
    expect(result.current[0].page).toBe(5);

    // Reset
    act(() => {
      result.current[1](DEFAULTS);
    });

    expect(result.current[0]).toEqual(DEFAULTS);
  });
});

// ── stateToParams clean URL generation ──

describe('stateToParams clean URL generation', () => {
  it('generates empty params for all defaults', () => {
    const params = stateToParams(DEFAULTS);
    expect(params.toString()).toBe('');
  });

  it('includes only non-default values', () => {
    const state: SearchState = {
      ...DEFAULTS,
      query: 'test',
      page: 2,
    };
    const params = stateToParams(state);
    expect(params.get('q')).toBe('test');
    expect(params.get('page')).toBe('2');
    expect(params.has('sort')).toBe(false);
    expect(params.has('mode')).toBe(false);
    expect(params.has('limit')).toBe(false);
  });

  it('does not include empty query', () => {
    const state: SearchState = { ...DEFAULTS, query: '' };
    const params = stateToParams(state);
    expect(params.has('q')).toBe(false);
  });

  it('serialises all filter types with prefix', () => {
    const state: SearchState = {
      ...DEFAULTS,
      query: 'test',
      filters: {
        author: 'A',
        category: 'B',
        language: 'C',
        year: '2024',
      },
    };
    const params = stateToParams(state);
    expect(params.get('filter_author')).toBe('A');
    expect(params.get('filter_category')).toBe('B');
    expect(params.get('filter_language')).toBe('C');
    expect(params.get('filter_year')).toBe('2024');
  });
});

// ── Comprehensive round-trip tests ──

describe('comprehensive round-trips', () => {
  it('round-trips a minimal state', () => {
    const state: SearchState = { ...DEFAULTS, query: 'hello' };
    expect(parseSearchParams(stateToParams(state))).toEqual(state);
  });

  it('round-trips a maximal state', () => {
    const state: SearchState = {
      query: 'advanced search',
      page: 10,
      sort: 'author_s asc',
      mode: 'hybrid',
      limit: 50,
      filters: {
        author: 'Alan Turing',
        category: 'Computer Science',
        language: 'English',
        year: '1950',
      },
    };
    expect(parseSearchParams(stateToParams(state))).toEqual(state);
  });

  it('round-trips with only filters set', () => {
    const state: SearchState = {
      ...DEFAULTS,
      filters: { language: 'French', year: '2023' },
    };
    expect(parseSearchParams(stateToParams(state))).toEqual(state);
  });

  it('round-trips with only page set', () => {
    const state: SearchState = { ...DEFAULTS, page: 42 };
    expect(parseSearchParams(stateToParams(state))).toEqual(state);
  });

  it('round-trips each valid limit', () => {
    for (const limit of [10, 20, 50]) {
      const state: SearchState = { ...DEFAULTS, limit };
      expect(parseSearchParams(stateToParams(state))).toEqual(state);
    }
  });
});
