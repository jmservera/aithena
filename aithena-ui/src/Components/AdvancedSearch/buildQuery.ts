export type SearchMode = "keyword" | "semantic" | "hybrid";
export type QueryOperator = "AND" | "OR" | "NOT";
export type QueryField = "all" | "title" | "author" | "content" | "category";

export interface QueryTerm {
  id: string;
  text: string;
  operator: QueryOperator;
  field: QueryField;
  fuzzy: boolean;
  phrase: boolean;
}

export interface YearRange {
  from: string;
  to: string;
}

export interface BuildQueryInput {
  terms: QueryTerm[];
  yearRange?: YearRange;
  language?: string;
}

export const QUERY_OPERATOR_OPTIONS: QueryOperator[] = ["AND", "OR", "NOT"];

export const QUERY_FIELD_OPTIONS: Array<{ value: QueryField; label: string }> =
  [
    { value: "all", label: "All fields" },
    { value: "title", label: "Title" },
    { value: "author", label: "Author" },
    { value: "content", label: "Content" },
    { value: "category", label: "Category" },
  ];

const FIELD_MAP: Record<Exclude<QueryField, "all">, string> = {
  title: "title_s",
  author: "author_s",
  content: "content",
  category: "category_s",
};

const SOLR_SPECIAL_CHARACTERS = /([+\-!(){}[\]^"~:\\/])/g;
const SOLR_BOOLEAN_TOKENS = /(&&|\|\|)/g;

function normalizeWhitespace(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function escapeSolrTerm(value: string): string {
  return normalizeWhitespace(value)
    .replace(SOLR_BOOLEAN_TOKENS, "\\$1")
    .replace(SOLR_SPECIAL_CHARACTERS, "\\$1");
}

function escapeSolrPhrase(value: string): string {
  return normalizeWhitespace(value).replace(/(["\\])/g, "\\$1");
}

function buildTermClause(term: QueryTerm): string {
  const normalizedText = normalizeWhitespace(term.text);
  if (!normalizedText) {
    return "";
  }

  const isMultiWord = normalizedText.includes(" ");
  const escapedText = term.phrase
    ? escapeSolrPhrase(normalizedText)
    : escapeSolrTerm(normalizedText);

  let clause = term.phrase ? `"${escapedText}"` : escapedText;
  if (!term.phrase && isMultiWord) {
    clause = `(${clause})`;
  }

  if (
    term.fuzzy &&
    !term.phrase &&
    !isMultiWord &&
    !/[?*]/.test(normalizedText)
  ) {
    clause = `${clause}~`;
  }

  if (term.field === "all") {
    return clause;
  }

  return `${FIELD_MAP[term.field]}:${clause}`;
}

function normalizeYearBoundary(value: string): string {
  const normalizedValue = value.trim();
  return /^-?\d+$/.test(normalizedValue) ? normalizedValue : "";
}

function buildYearRangeClause(yearRange?: YearRange): string {
  if (!yearRange) {
    return "";
  }

  const from = normalizeYearBoundary(yearRange.from);
  const to = normalizeYearBoundary(yearRange.to);

  if (!from && !to) {
    return "";
  }

  return `year_i:[${from || "*"} TO ${to || "*"}]`;
}

function buildLanguageClause(language?: string): string {
  const normalizedLanguage = language?.trim();
  if (!normalizedLanguage) {
    return "";
  }

  const escapedLanguage = escapeSolrTerm(normalizedLanguage);
  return `(language_detected_s:${escapedLanguage} OR language_s:${escapedLanguage})`;
}

export function buildQuery({
  terms,
  yearRange,
  language,
}: BuildQueryInput): string {
  const termClauses = terms
    .map((term) => ({ term, clause: buildTermClause(term) }))
    .filter((entry) => entry.clause);

  const segments: string[] = [];

  if (termClauses.length > 0) {
    const [firstTerm, ...otherTerms] = termClauses;
    let combinedTerms = firstTerm.clause;

    for (const { term, clause } of otherTerms) {
      if (term.operator === "NOT") {
        combinedTerms = `${combinedTerms} NOT ${clause}`;
      } else {
        combinedTerms = `${combinedTerms} ${term.operator} ${clause}`;
      }
    }

    segments.push(combinedTerms);
  }

  const yearClause = buildYearRangeClause(yearRange);
  if (yearClause) {
    segments.push(yearClause);
  }

  const languageClause = buildLanguageClause(language);
  if (languageClause) {
    segments.push(languageClause);
  }

  return segments.length > 0 ? segments.join(" AND ") : "*:*";
}
