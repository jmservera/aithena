import { FormEvent, useMemo, useRef, useState } from "react";
import LanguageFilter from "./LanguageFilter";
import QueryPreview from "./QueryPreview";
import QueryTermRow from "./QueryTermRow";
import SearchModeSelector from "./SearchModeSelector";
import YearRangeFilter from "./YearRangeFilter";
import { QueryTerm, SearchMode, YearRange, buildQuery } from "./buildQuery";

interface SearchSubmission {
  mode: SearchMode;
  query: string;
  keywordQuery: string;
  semanticQuery: string;
}

interface AdvancedSearchBuilderProps {
  languages?: string[];
  loading?: boolean;
  onSearch: (submission: SearchSubmission) => void;
  semanticEnabled?: boolean;
  hybridEnabled?: boolean;
}

const FALLBACK_LANGUAGES = ["ca", "en", "es", "fr"];

function createEmptyTerm(index: number): QueryTerm {
  return {
    id: `term-${index}`,
    text: "",
    operator: "AND",
    field: "all",
    fuzzy: false,
    phrase: false,
  };
}

function AdvancedSearchBuilder({
  languages = [],
  loading = false,
  onSearch,
  semanticEnabled = false,
  hybridEnabled = false,
}: AdvancedSearchBuilderProps) {
  const [builderMode, setBuilderMode] = useState<"simple" | "advanced">(
    "simple"
  );
  const [searchMode, setSearchMode] = useState<SearchMode>("keyword");
  const [simpleQuery, setSimpleQuery] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [yearRange, setYearRange] = useState<YearRange>({ from: "", to: "" });
  const [language, setLanguage] = useState("");
  const [terms, setTerms] = useState<QueryTerm[]>([createEmptyTerm(0)]);
  const nextTermId = useRef(1);

  const enabledModes = useMemo(() => {
    const modes: SearchMode[] = ["keyword"];
    if (semanticEnabled) {
      modes.push("semantic");
    }
    if (hybridEnabled) {
      modes.push("hybrid");
    }
    return modes;
  }, [hybridEnabled, semanticEnabled]);

  const keywordQuery = useMemo(
    () => buildQuery({ terms, yearRange, language }),
    [language, terms, yearRange]
  );

  const languageOptions = useMemo(
    () => Array.from(new Set([...languages, ...FALLBACK_LANGUAGES])),
    [languages]
  );

  const showAdvancedBuilder = builderMode === "advanced";
  const showKeywordBuilder = showAdvancedBuilder && searchMode !== "semantic";
  const showSemanticInput = showAdvancedBuilder && searchMode !== "keyword";

  function handleBuilderModeChange(nextMode: "simple" | "advanced") {
    if (
      nextMode === "advanced" &&
      !terms[0]?.text.trim() &&
      simpleQuery.trim()
    ) {
      setTerms((currentTerms) => [
        { ...currentTerms[0], text: simpleQuery.trim() },
        ...currentTerms.slice(1),
      ]);
    }

    if (nextMode === "simple") {
      setSimpleQuery(keywordQuery === "*:*" ? "" : keywordQuery);
    }

    setBuilderMode(nextMode);
  }

  function handleModeChange(nextMode: SearchMode) {
    if (!enabledModes.includes(nextMode)) {
      return;
    }

    setSearchMode(nextMode);
    if (nextMode === "semantic" && !semanticQuery.trim()) {
      setSemanticQuery(simpleQuery.trim() || terms[0]?.text.trim() || "");
    }
  }

  function handleTermChange(id: string, updates: Partial<QueryTerm>) {
    setTerms((currentTerms) =>
      currentTerms.map((term) =>
        term.id === id ? { ...term, ...updates } : term
      )
    );
  }

  function handleAddTerm() {
    setTerms((currentTerms) => [
      ...currentTerms,
      createEmptyTerm(nextTermId.current++),
    ]);
  }

  function handleRemoveTerm(id: string) {
    setTerms((currentTerms) => {
      if (currentTerms.length === 1) {
        return currentTerms;
      }
      return currentTerms.filter((term) => term.id !== id);
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!showAdvancedBuilder) {
      onSearch({
        mode: "keyword",
        query: simpleQuery.trim(),
        keywordQuery: simpleQuery.trim(),
        semanticQuery: "",
      });
      return;
    }

    if (searchMode === "semantic") {
      const naturalLanguageQuery = semanticQuery.trim();
      onSearch({
        mode: searchMode,
        query: naturalLanguageQuery,
        keywordQuery,
        semanticQuery: naturalLanguageQuery,
      });
      return;
    }

    if (searchMode === "hybrid") {
      const naturalLanguageQuery = semanticQuery.trim();
      onSearch({
        mode: searchMode,
        query: naturalLanguageQuery || keywordQuery,
        keywordQuery,
        semanticQuery: naturalLanguageQuery,
      });
      return;
    }

    onSearch({
      mode: searchMode,
      query: keywordQuery,
      keywordQuery,
      semanticQuery: semanticQuery.trim(),
    });
  }

  return (
    <form className="advanced-search-builder" onSubmit={handleSubmit}>
      <div className="advanced-search-toolbar card border-0 shadow-sm">
        <div className="card-body d-flex flex-column gap-3">
          <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 align-items-lg-center">
            <div>
              <div className="advanced-search-title">Search composer</div>
              <p className="advanced-search-subtitle mb-0">
                Start with simple search, then opt into guided Solr query
                building.
              </p>
            </div>
            <div
              className="btn-group advanced-builder-toggle"
              role="group"
              aria-label="Search builder mode"
            >
              <button
                type="button"
                className={`btn ${builderMode === "simple" ? "btn-info" : "btn-outline-secondary"}`}
                onClick={() => handleBuilderModeChange("simple")}
              >
                Simple
              </button>
              <button
                type="button"
                className={`btn ${builderMode === "advanced" ? "btn-info" : "btn-outline-secondary"}`}
                onClick={() => handleBuilderModeChange("advanced")}
              >
                Advanced
              </button>
            </div>
          </div>

          {!showAdvancedBuilder && (
            <div className="search-form advanced-search-simple-form">
              <input
                className="search-input form-control"
                type="search"
                value={simpleQuery}
                placeholder="Search books by title, author, or content…"
                onChange={(event) => setSimpleQuery(event.target.value)}
                aria-label="Search query"
              />
              <button
                className="search-btn btn btn-info"
                type="submit"
                disabled={loading}
              >
                {loading ? "…" : "Search"}
              </button>
            </div>
          )}
        </div>
      </div>

      {showAdvancedBuilder && (
        <div className="advanced-search-panel card border-0 shadow-sm">
          <div className="card-body d-flex flex-column gap-4">
            <SearchModeSelector
              mode={searchMode}
              enabledModes={enabledModes}
              onChange={handleModeChange}
            />

            {showKeywordBuilder && (
              <div className="d-flex flex-column gap-3">
                <div className="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-2">
                  <div>
                    <div className="advanced-search-section-label">
                      Search terms
                    </div>
                    <p className="advanced-search-help mb-0">
                      Use rows to combine terms with AND / OR / NOT. Wildcards
                      like <code>*</code> and <code>?</code> can be typed
                      directly.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-outline-info align-self-start"
                    onClick={handleAddTerm}
                  >
                    Add term
                  </button>
                </div>

                {terms.map((term, index) => (
                  <QueryTermRow
                    key={term.id}
                    index={index}
                    term={term}
                    canRemove={terms.length > 1}
                    onChange={handleTermChange}
                    onRemove={handleRemoveTerm}
                  />
                ))}

                <div className="row g-3">
                  <div className="col-12 col-lg-6">
                    <YearRangeFilter
                      value={yearRange}
                      onChange={setYearRange}
                    />
                  </div>
                  <div className="col-12 col-lg-6">
                    <LanguageFilter
                      value={language}
                      options={languageOptions}
                      onChange={setLanguage}
                    />
                  </div>
                </div>
              </div>
            )}

            {showSemanticInput && (
              <div>
                <label
                  className="form-label advanced-search-section-label"
                  htmlFor="semantic-query-input"
                >
                  Natural language query
                </label>
                <textarea
                  id="semantic-query-input"
                  className="form-control advanced-semantic-input"
                  rows={searchMode === "hybrid" ? 3 : 4}
                  value={semanticQuery}
                  placeholder="Describe the kind of book or passage you want to find…"
                  onChange={(event) => setSemanticQuery(event.target.value)}
                />
              </div>
            )}

            <QueryPreview
              mode={searchMode}
              keywordQuery={keywordQuery}
              semanticQuery={semanticQuery}
            />

            <div className="d-flex justify-content-end">
              <button
                className="search-btn btn btn-info"
                type="submit"
                disabled={loading}
              >
                {loading ? "…" : "Search"}
              </button>
            </div>
          </div>
        </div>
      )}
    </form>
  );
}

export type { SearchSubmission };
export default AdvancedSearchBuilder;
