import { useEffect, useState } from 'react';

import { apiFetch, buildApiUrl } from '../api';
import { BookResult } from './search';

export interface UseBookDetailResult {
  book: BookResult | null;
  loading: boolean;
  error: string | null;
}

export function useBookDetail(
  bookId: string | null,
  initialData?: BookResult | null
): UseBookDetailResult {
  const [book, setBook] = useState<BookResult | null>(initialData ?? null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bookId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setBook(null);
      setLoading(false);
      setError(null);
      return;
    }

    if (initialData) {
      setBook(initialData);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();

    async function fetchBookDetail() {
      setLoading(true);
      setError(null);

      try {
        const url = buildApiUrl(`/v1/books/${encodeURIComponent(bookId!)}`);
        const response = await apiFetch(url, { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`Book detail request failed: ${response.status}`);
        }

        const data: BookResult = await response.json();
        if (!cancelled) {
          setBook(data);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === 'AbortError')) {
          setError(err instanceof Error ? err.message : 'Failed to load book details');
          setBook(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchBookDetail();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId, initialData]);

  return { book, loading, error };
}
