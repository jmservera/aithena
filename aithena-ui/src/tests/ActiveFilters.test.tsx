import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ActiveFilters from "../Components/ActiveFilters";
import { SearchFilters } from "../hooks/search";

describe("ActiveFilters", () => {
  it("renders nothing when no filters are active", () => {
    const { container } = render(
      <ActiveFilters filters={{}} onRemove={vi.fn()} onClearAll={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders a chip for each active filter", () => {
    const filters: SearchFilters = { author: "Tolkien", language: "English" };
    render(
      <ActiveFilters
        filters={filters}
        onRemove={vi.fn()}
        onClearAll={vi.fn()}
      />
    );
    expect(screen.getByText("Tolkien")).toBeInTheDocument();
    expect(screen.getByText("English")).toBeInTheDocument();
  });

  it("shows 'Clear all' button only when more than one filter is active", () => {
    const singleFilter: SearchFilters = { author: "Tolkien" };
    const { rerender } = render(
      <ActiveFilters
        filters={singleFilter}
        onRemove={vi.fn()}
        onClearAll={vi.fn()}
      />
    );
    expect(screen.queryByRole("button", { name: /clear all/i })).toBeNull();

    const multiFilter: SearchFilters = { author: "Tolkien", language: "English" };
    rerender(
      <ActiveFilters
        filters={multiFilter}
        onRemove={vi.fn()}
        onClearAll={vi.fn()}
      />
    );
    expect(
      screen.getByRole("button", { name: /clear all/i })
    ).toBeInTheDocument();
  });

  it("calls onRemove with the correct key when a chip remove button is clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    const filters: SearchFilters = { author: "Tolkien" };
    render(
      <ActiveFilters
        filters={filters}
        onRemove={onRemove}
        onClearAll={vi.fn()}
      />
    );
    await user.click(screen.getByRole("button", { name: /remove author/i }));
    expect(onRemove).toHaveBeenCalledWith("author");
  });

  it("calls onClearAll when the 'Clear all' button is clicked", async () => {
    const user = userEvent.setup();
    const onClearAll = vi.fn();
    const filters: SearchFilters = {
      author: "Tolkien",
      category: "Fiction",
    };
    render(
      <ActiveFilters
        filters={filters}
        onRemove={vi.fn()}
        onClearAll={onClearAll}
      />
    );
    await user.click(screen.getByRole("button", { name: /clear all/i }));
    expect(onClearAll).toHaveBeenCalledOnce();
  });
});
