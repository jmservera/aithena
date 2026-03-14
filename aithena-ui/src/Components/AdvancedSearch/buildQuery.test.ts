import { describe, expect, it } from "vitest";
import { buildQuery } from "./buildQuery";

describe("buildQuery", () => {
  it("adds a fuzzy suffix for single-term searches", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: "folklore",
            field: "all",
            operator: "AND",
            fuzzy: true,
            phrase: false,
          },
        ],
      })
    ).toBe("folklore~");
  });

  it("builds field-specific phrase clauses", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: "catalan folklore",
            field: "title",
            operator: "AND",
            fuzzy: false,
            phrase: true,
          },
        ],
      })
    ).toBe('title_s:"catalan folklore"');
  });

  it("combines boolean operators, year range, and language filters", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: "folklore",
            field: "all",
            operator: "AND",
            fuzzy: false,
            phrase: false,
          },
          {
            id: "term-1",
            text: "Joan Amades",
            field: "author",
            operator: "AND",
            fuzzy: false,
            phrase: true,
          },
          {
            id: "term-2",
            text: "children",
            field: "content",
            operator: "NOT",
            fuzzy: false,
            phrase: false,
          },
        ],
        yearRange: { from: "1900", to: "1950" },
        language: "ca",
      })
    ).toBe(
      'folklore AND author_s:"Joan Amades" NOT content:children AND year_i:[1900 TO 1950] AND (language_detected_s:ca OR language_s:ca)'
    );
  });

  it("supports open-ended year ranges and filter-only queries", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: "",
            field: "all",
            operator: "AND",
            fuzzy: false,
            phrase: false,
          },
        ],
        yearRange: { from: "1900", to: "" },
        language: "en",
      })
    ).toBe("year_i:[1900 TO *] AND (language_detected_s:en OR language_s:en)");
  });

  it("ignores invalid year boundary values instead of generating broken Solr ranges", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: "history",
            field: "all",
            operator: "AND",
            fuzzy: false,
            phrase: false,
          },
        ],
        yearRange: { from: "1900.5", to: "1950" },
      })
    ).toBe("history AND year_i:[* TO 1950]");
  });

  it("returns match-all when no terms or filters are provided", () => {
    expect(
      buildQuery({
        terms: [
          {
            id: "term-0",
            text: " ",
            field: "all",
            operator: "AND",
            fuzzy: false,
            phrase: false,
          },
        ],
        yearRange: { from: "", to: "" },
        language: "",
      })
    ).toBe("*:*");
  });
});
