import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FacetPanel from "../Components/FacetPanel";
import { FacetGroups, SearchFilters } from "../hooks/search";

const FACETS: FacetGroups = {
  author: [
    { value: "Tolkien", count: 5 },
    { value: "Asimov", count: 3 },
  ],
  category: [{ value: "Fiction", count: 8 }],
  language: [{ value: "English", count: 10 }],
};

describe("FacetPanel", () => {
  it("renders facet groups with labels and counts", () => {
    render(
      <FacetPanel facets={FACETS} filters={{}} onFilterChange={vi.fn()} />
    );
    expect(screen.getByText("Author")).toBeInTheDocument();
    expect(screen.getByText("Tolkien")).toBeInTheDocument();
    expect(screen.getByText("(5)")).toBeInTheDocument();
    expect(screen.getByText("Asimov")).toBeInTheDocument();
    expect(screen.getByText("(3)")).toBeInTheDocument();
    expect(screen.getByText("Category")).toBeInTheDocument();
    expect(screen.getByText("Fiction")).toBeInTheDocument();
  });

  it("does not render empty facet groups", () => {
    render(
      <FacetPanel
        facets={{ author: [], category: [{ value: "Fiction", count: 2 }] }}
        filters={{}}
        onFilterChange={vi.fn()}
      />
    );
    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.getByText("Category")).toBeInTheDocument();
  });

  it("renders checkboxes unchecked when no filter is active", () => {
    render(
      <FacetPanel facets={FACETS} filters={{}} onFilterChange={vi.fn()} />
    );
    const checkboxes = screen.getAllByRole("checkbox");
    checkboxes.forEach((cb) => expect(cb).not.toBeChecked());
  });

  it("renders the active filter checkbox as checked", () => {
    const filters: SearchFilters = { author: "Tolkien" };
    render(
      <FacetPanel facets={FACETS} filters={filters} onFilterChange={vi.fn()} />
    );
    const tolkienCheckbox = screen.getByRole("checkbox", { name: /Tolkien/ });
    expect(tolkienCheckbox).toBeChecked();
    const asimovCheckbox = screen.getByRole("checkbox", { name: /Asimov/ });
    expect(asimovCheckbox).not.toBeChecked();
  });

  it("calls onFilterChange with the value when an unchecked facet is clicked", async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    render(
      <FacetPanel
        facets={FACETS}
        filters={{}}
        onFilterChange={onFilterChange}
      />
    );
    await user.click(screen.getByRole("checkbox", { name: /Tolkien/ }));
    expect(onFilterChange).toHaveBeenCalledWith("author", "Tolkien");
  });

  it("calls onFilterChange with undefined when an active facet is clicked (deselect)", async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    const filters: SearchFilters = { author: "Tolkien" };
    render(
      <FacetPanel
        facets={FACETS}
        filters={filters}
        onFilterChange={onFilterChange}
      />
    );
    await user.click(screen.getByRole("checkbox", { name: /Tolkien/ }));
    expect(onFilterChange).toHaveBeenCalledWith("author", undefined);
  });
});
