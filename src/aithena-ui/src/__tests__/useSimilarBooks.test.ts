import { describe, it, beforeEach, expect } from 'vitest';
import {
  MAX_CACHE_SIZE,
  getCachedSimilarBook,
  cacheSimilarBooks,
  clearSimilarBookCache,
  getSimilarBookCacheSize,
  SimilarBook,
} from '../hooks/similarBooks';

function makeBook(id: string): SimilarBook {
  return { id, title: `Book ${id}`, author: 'Author', score: 0.5 };
}

describe('useSimilarBooks LRU cache', () => {
  beforeEach(() => {
    clearSimilarBookCache();
  });

  it('MAX_CACHE_SIZE is 100', () => {
    expect(MAX_CACHE_SIZE).toBe(100);
  });

  it('caches books and returns them via getCachedSimilarBook', () => {
    const book = makeBook('book-1');
    cacheSimilarBooks([book]);
    expect(getCachedSimilarBook('book-1')).toEqual(book);
  });

  it('returns undefined for an uncached book', () => {
    expect(getCachedSimilarBook('missing')).toBeUndefined();
  });

  it('does not evict entries when the cache is at capacity', () => {
    const books = Array.from({ length: MAX_CACHE_SIZE }, (_, i) => makeBook(`book-${i}`));
    cacheSimilarBooks(books);
    expect(getSimilarBookCacheSize()).toBe(MAX_CACHE_SIZE);
    expect(getCachedSimilarBook('book-0')).toBeDefined();
  });

  it('evicts the least-recently-used entry when the limit is exceeded', () => {
    // Fill cache to capacity
    const books = Array.from({ length: MAX_CACHE_SIZE }, (_, i) => makeBook(`book-${i}`));
    cacheSimilarBooks(books);

    // Adding one more should evict book-0 (oldest / LRU)
    cacheSimilarBooks([makeBook('book-new')]);

    expect(getSimilarBookCacheSize()).toBe(MAX_CACHE_SIZE);
    expect(getCachedSimilarBook('book-0')).toBeUndefined();
    expect(getCachedSimilarBook('book-new')).toBeDefined();
  });

  it('refreshes access order so a recently accessed entry is not evicted', () => {
    // Fill to capacity
    const books = Array.from({ length: MAX_CACHE_SIZE }, (_, i) => makeBook(`book-${i}`));
    cacheSimilarBooks(books);

    // Access book-0 to make it most-recently-used
    getCachedSimilarBook('book-0');

    // Adding a new entry should evict book-1 (now the LRU), not book-0
    cacheSimilarBooks([makeBook('book-new')]);

    expect(getSimilarBookCacheSize()).toBe(MAX_CACHE_SIZE);
    expect(getCachedSimilarBook('book-0')).toBeDefined();
    expect(getCachedSimilarBook('book-1')).toBeUndefined();
    expect(getCachedSimilarBook('book-new')).toBeDefined();
  });

  it('cache size never exceeds MAX_CACHE_SIZE after many insertions', () => {
    const books = Array.from({ length: MAX_CACHE_SIZE * 3 }, (_, i) => makeBook(`book-${i}`));
    cacheSimilarBooks(books);
    expect(getSimilarBookCacheSize()).toBeLessThanOrEqual(MAX_CACHE_SIZE);
  });

  it('evicts entries in FIFO order when multiple entries overflow', () => {
    const books = Array.from({ length: MAX_CACHE_SIZE }, (_, i) => makeBook(`book-${i}`));
    cacheSimilarBooks(books);

    // Add 5 more to trigger 5 evictions
    const extra = Array.from({ length: 5 }, (_, i) => makeBook(`extra-${i}`));
    cacheSimilarBooks(extra);

    // The 5 oldest entries (book-0 through book-4) should be gone
    for (let i = 0; i < 5; i++) {
      expect(getCachedSimilarBook(`book-${i}`)).toBeUndefined();
    }
    expect(getCachedSimilarBook('book-5')).toBeDefined();
  });
});
