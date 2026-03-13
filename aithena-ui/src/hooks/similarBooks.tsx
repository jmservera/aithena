import { useState, useCallback } from "react";

const similarBooksBaseURL = `${import.meta.env.VITE_API_URL}/v1/books/`;

export interface SimilarBook {
  id: string;
  title: string;
  author: string;
  year?: number;
  category?: string;
  document_url?: string;
  score: number;
}

export interface SimilarBooksResponse {
  results: SimilarBook[];
  total: number;
}

export type SimilarBooksState = "idle" | "loading" | "success" | "error";

export const useSimilarBooks = () => {
  const [similar, setSimilar] = useState<SimilarBook[]>([]);
  const [state, setState] = useState<SimilarBooksState>("idle");
  const [error, setError] = useState<string | null>(null);

  // Fetch up to 5 similar books — a smaller default than search (10) because
  // the related-books panel is a compact sidebar widget, not a primary results list.
  const fetchSimilar = useCallback(async (bookId: string, limit = 5) => {
    setState("loading");
    setError(null);
    setSimilar([]);

    try {
      const url = new URL(
        `${similarBooksBaseURL}${encodeURIComponent(bookId)}/similar`
      );
      url.searchParams.set("limit", String(limit));

      const response = await fetch(url.toString(), {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(
          `Failed to load similar books: ${response.status} ${response.statusText}`
        );
      }

      const data: SimilarBooksResponse = await response.json();
      setSimilar(data.results ?? []);
      setState("success");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      );
      setSimilar([]);
      setState("error");
    }
  }, []);

  const reset = useCallback(() => {
    setSimilar([]);
    setState("idle");
    setError(null);
  }, []);

  return { similar, state, error, fetchSimilar, reset };
};
