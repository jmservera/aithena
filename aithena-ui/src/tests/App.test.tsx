import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { SearchResponse } from "../hooks/search";

// ── helpers ──────────────────────────────────────────────────────────────────

function mockFetch(response: SearchResponse) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
}

function mockFetchError(status = 500) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("Internal Server Error", { status })
  );
}

const EMPTY_RESPONSE: SearchResponse = {
  results: [],
  total: 0,
  query: "nothing",
  facets: {},
  page: 1,
  limit: 10,
};

const BOOKS_RESPONSE: SearchResponse = {
  results: [
    {
      id: "b1",
      title: "The Fellowship of the Ring",
      author: "Tolkien",
      year: 1954,
      category: "Fantasy",
      language: "English",
      document_url: "/docs/fotr.pdf",
    },
    {
      id: "b2",
      title: "Foundation",
      author: "Asimov",
      year: 1951,
      category: "SciFi",
      language: "English",
      document_url: null,
    },
  ],
  total: 2,
  query: "books",
  facets: {
    author: [
      { value: "Tolkien", count: 1 },
      { value: "Asimov", count: 1 },
    ],
    category: [
      { value: "Fantasy", count: 1 },
      { value: "SciFi", count: 1 },
    ],
    language: [{ value: "English", count: 2 }],
  },
  page: 1,
  limit: 10,
};

// ── tests ─────────────────────────────────────────────────────────────────────

describe("App — search", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the search form on load without making any fetch calls", () => {
    render(<App />);
    expect(
      screen.getByRole("searchbox", { name: /search query/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /search/i })
    ).toBeInTheDocument();
  });

  it("shows empty-state prompt before any query is submitted", () => {
    render(<App />);
    expect(
      screen.getByText(/enter a search term above/i)
    ).toBeInTheDocument();
  });

  it("submits a search on form submit and renders results", async () => {
    const user = userEvent.setup();
    mockFetch(BOOKS_RESPONSE);

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "books"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByText("The Fellowship of the Ring")).toBeInTheDocument()
    );
    expect(screen.getByText("Foundation")).toBeInTheDocument();
  });

  it("displays the result count summary after a successful search", async () => {
    const user = userEvent.setup();
    mockFetch(BOOKS_RESPONSE);

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "books"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByText(/2 results for/i)).toBeInTheDocument()
    );
  });

  it("shows empty-state message when search returns no results", async () => {
    const user = userEvent.setup();
    mockFetch(EMPTY_RESPONSE);

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "nothing"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByText(/no results found/i)).toBeInTheDocument()
    );
  });

  it("shows an error alert when the API returns an error status", async () => {
    const user = userEvent.setup();
    mockFetchError();

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "books"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
  });
});

describe("App — facets", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function renderAfterSearch() {
    const user = userEvent.setup();
    mockFetch(BOOKS_RESPONSE);

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "books"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByText("The Fellowship of the Ring")).toBeInTheDocument()
    );
    return user;
  }

  it("renders facet groups after a successful search", async () => {
    await renderAfterSearch();
    expect(screen.getByText("Author")).toBeInTheDocument();
    // "Tolkien" appears as a facet value in the sidebar
    expect(screen.getByText("Tolkien", { selector: ".facet-value" })).toBeInTheDocument();
    expect(screen.getByText("Category")).toBeInTheDocument();
  });

  it("selecting a facet adds it as an active filter chip", async () => {
    const user = await renderAfterSearch();

    // Second fetch with the filter applied
    mockFetch({
      ...BOOKS_RESPONSE,
      results: [BOOKS_RESPONSE.results[0]],
      total: 1,
    });

    const tolkienCheckbox = screen.getByRole("checkbox", { name: /Tolkien/ });
    await user.click(tolkienCheckbox);

    await waitFor(() =>
      expect(screen.getByText("Tolkien", { selector: ".filter-chip-value" })).toBeInTheDocument()
    );
  });

  it("deselecting a facet removes its active filter chip", async () => {
    const user = await renderAfterSearch();

    // Filter applied
    mockFetch({
      ...BOOKS_RESPONSE,
      results: [BOOKS_RESPONSE.results[0]],
      total: 1,
    });
    await user.click(screen.getByRole("checkbox", { name: /Tolkien/ }));
    await waitFor(() =>
      expect(screen.getByText("Tolkien", { selector: ".filter-chip-value" })).toBeInTheDocument()
    );

    // Filter removed
    mockFetch(BOOKS_RESPONSE);
    await user.click(screen.getByRole("checkbox", { name: /Tolkien/ }));
    await waitFor(() =>
      expect(
        screen.queryByText("Tolkien", { selector: ".filter-chip-value" })
      ).not.toBeInTheDocument()
    );
  });

  it("'Clear all' button removes all active filter chips", async () => {
    const user = await renderAfterSearch();

    // Apply two filters in sequence
    mockFetch({ ...BOOKS_RESPONSE, results: [BOOKS_RESPONSE.results[0]], total: 1 });
    await user.click(screen.getByRole("checkbox", { name: /Tolkien/ }));
    await waitFor(() => screen.getByText("Tolkien", { selector: ".filter-chip-value" }));

    mockFetch({ ...BOOKS_RESPONSE, results: [BOOKS_RESPONSE.results[0]], total: 1 });
    await user.click(screen.getByRole("checkbox", { name: /Fantasy/ }));
    await waitFor(() => screen.getByRole("button", { name: /clear all/i }));

    // Clear all
    mockFetch(BOOKS_RESPONSE);
    await user.click(screen.getByRole("button", { name: /clear all/i }));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /clear all/i })
      ).not.toBeInTheDocument()
    );
  });
});

describe("App — PDF viewer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function renderAfterSearch() {
    const user = userEvent.setup();
    mockFetch(BOOKS_RESPONSE);

    render(<App />);
    await user.type(
      screen.getByRole("searchbox", { name: /search query/i }),
      "books"
    );
    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() =>
      expect(screen.getByText("The Fellowship of the Ring")).toBeInTheDocument()
    );
    return user;
  }

  it("PDF viewer is not shown before a book is selected", async () => {
    await renderAfterSearch();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("clicking 'Open PDF' opens the viewer dialog", async () => {
    const user = await renderAfterSearch();
    await user.click(
      screen.getByRole("button", { name: /open pdf for the fellowship/i })
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByTitle("The Fellowship of the Ring")).toBeInTheDocument();
  });

  it("clicking the close button hides the viewer", async () => {
    const user = await renderAfterSearch();
    await user.click(
      screen.getByRole("button", { name: /open pdf for the fellowship/i })
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /close pdf viewer/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("pressing Escape closes the viewer", async () => {
    const user = await renderAfterSearch();
    await user.click(
      screen.getByRole("button", { name: /open pdf for the fellowship/i })
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).toBeNull()
    );
  });
});
