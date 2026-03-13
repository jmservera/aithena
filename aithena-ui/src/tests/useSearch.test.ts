import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSearch } from "../hooks/search";
import { SearchResponse } from "../hooks/search";

const MOCK_RESPONSE: SearchResponse = {
  results: [
    { id: "1", title: "Dune", author: "Herbert", year: 1965, document_url: null },
  ],
  total: 1,
  query: "dune",
  facets: {
    author: [{ value: "Herbert", count: 1 }],
    language: [{ value: "English", count: 1 }],
  },
  page: 1,
  limit: 10,
};

function mockFetch(response: SearchResponse, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(response), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  );
}

describe("useSearch hook", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts in the idle state with empty results", () => {
    const { result } = renderHook(() => useSearch());
    expect(result.current.results).toHaveLength(0);
    expect(result.current.total).toBe(0);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("does not call fetch when query is empty", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { result } = renderHook(() => useSearch());
    // Initial render: query is "" so fetch should not be called
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fetches results when a query is set", async () => {
    mockFetch(MOCK_RESPONSE);
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("dune");
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.results).toHaveLength(1);
    expect(result.current.results[0].title).toBe("Dune");
    expect(result.current.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("includes facets in the API response", async () => {
    mockFetch(MOCK_RESPONSE);
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("dune");
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.facets.author).toHaveLength(1);
    expect(result.current.facets.author![0].value).toBe("Herbert");
  });

  it("sets error state on a non-OK API response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("Server Error", { status: 500 })
    );
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("bad");
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.results).toHaveLength(0);
  });

  it("applies a filter by updating search params", async () => {
    const fetchSpy = mockFetch(MOCK_RESPONSE);
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("dune");
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.setFilter("author", "Herbert");
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    const lastCall = fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1][0] as string;
    expect(lastCall).toContain("fq_author=Herbert");
  });

  it("resets page to 1 when a filter is changed", async () => {
    mockFetch(MOCK_RESPONSE);
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("dune");
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.setPage(3);
    });
    await waitFor(() =>
      expect(result.current.searchState.page).toBe(3)
    );

    act(() => {
      result.current.setFilter("author", "Herbert");
    });
    await waitFor(() =>
      expect(result.current.searchState.page).toBe(1)
    );
  });

  it("clears all filters with clearFilters", async () => {
    mockFetch(MOCK_RESPONSE);
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.setQuery("dune");
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.setFilter("author", "Herbert");
    });
    await waitFor(() =>
      expect(result.current.searchState.filters.author).toBe("Herbert")
    );

    act(() => {
      result.current.clearFilters();
    });
    await waitFor(() =>
      expect(result.current.searchState.filters).toEqual({})
    );
  });
});
