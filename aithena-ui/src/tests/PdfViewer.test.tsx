import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PdfViewer from "../Components/PdfViewer";
import { BookResult } from "../hooks/search";

const BOOK: BookResult = {
  id: "book-1",
  title: "The Hobbit",
  author: "Tolkien",
  document_url: "/docs/the-hobbit.pdf",
};

const BOOK_NO_URL: BookResult = {
  id: "book-2",
  title: "Unknown",
  document_url: null,
};

describe("PdfViewer", () => {
  it("renders the viewer dialog with the book title", () => {
    render(<PdfViewer result={BOOK} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("The Hobbit")).toBeInTheDocument();
    expect(screen.getByText(/Tolkien/)).toBeInTheDocument();
  });

  it("renders an iframe when document_url is provided", () => {
    render(<PdfViewer result={BOOK} onClose={vi.fn()} />);
    const iframe = screen.getByTitle("The Hobbit");
    expect(iframe).toBeInTheDocument();
    expect(iframe.tagName).toBe("IFRAME");
  });

  it("renders an error message when document_url is null", () => {
    render(<PdfViewer result={BOOK_NO_URL} onClose={vi.fn()} />);
    expect(
      screen.getByText(/no document url available/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole("iframe")).toBeNull();
  });

  it("calls onClose when the close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<PdfViewer result={BOOK} onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: /close pdf viewer/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the Escape key is pressed", () => {
    const onClose = vi.fn();
    render(<PdfViewer result={BOOK} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose for keys other than Escape", () => {
    const onClose = vi.fn();
    render(<PdfViewer result={BOOK} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
