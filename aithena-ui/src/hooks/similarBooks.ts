import { useEffect, useState } from 'react';

import { buildApiUrl } from '../api';

const DEFAULT_LIMIT = 5;
const DEFAULT_MIN_SCORE = 0.0;

export interface SimilarBook {
  id: string;
  title: string;
  author: string;
  year?: number;
  category?: string;
  document_url?: string | null;
  score: number;
}

interface SimilarBooksResponse {
  results?: SimilarBook[];
}

export interface UseSimilarBooksResult {
  books: SimilarBook[];
  loading: boolean;
  error: string | null;
}

const similarBookCache = new Map<string, SimilarBook>();

export function getCachedSimilarBook(bookId: string): SimilarBook | undefined {
  return similarBookCache.get(bookId);
}

function cacheSimilarBooks(books: SimilarBook[]): void {
  books.forEach((book) => {
    similarBookCache.set(book.id, book);
  });
}

function buildSimilarBooksUrl(documentId: string): string {
  const params = new URLSearchParams({
    limit: DEFAULT_LIMIT.toString(),
    min_score: DEFAULT_MIN_SCORE.toString(),
  });

  return `${buildApiUrl(`/v1/books/${encodeURIComponent(documentId)}/similar`)}?${params.toString()}`;
}

export function useSimilarBooks(documentId: string | null): UseSimilarBooksResult {
  const [books, setBooks] = useState<SimilarBook[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) {
      setBooks([]);
      setLoading(false);
      setError(null);
      return;
    }

    const currentDocumentId = documentId;
    let cancelled = false;
    const controller = new AbortController();

    async function fetchSimilarBooks() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(buildSimilarBooksUrl(currentDocumentId), {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Similar books request failed: ${response.status}`);
        }

        const data: SimilarBooksResponse = await response.json();
        const nextBooks = data.results ?? [];

        if (!cancelled) {
          cacheSimilarBooks(nextBooks);
          setBooks(nextBooks);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === 'AbortError')) {
          setError(err instanceof Error ? err.message : 'Failed to load similar books');
          setBooks([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchSimilarBooks();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [documentId]);

  return { books, loading, error };
}
