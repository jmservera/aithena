import {
  QUERY_FIELD_OPTIONS,
  QUERY_OPERATOR_OPTIONS,
  QueryTerm,
} from "./buildQuery";

interface QueryTermRowProps {
  index: number;
  term: QueryTerm;
  canRemove: boolean;
  onChange: (id: string, updates: Partial<QueryTerm>) => void;
  onRemove: (id: string) => void;
}

function QueryTermRow({
  index,
  term,
  canRemove,
  onChange,
  onRemove,
}: QueryTermRowProps) {
  const fuzzyDisabled = term.phrase;

  return (
    <div className="advanced-term-row card border-0 shadow-sm">
      <div className="card-body">
        <div className="row g-3 align-items-end">
          <div className="col-12 col-xl-4">
            <label
              className="form-label advanced-search-label"
              htmlFor={`query-term-${term.id}`}
            >
              Search term
            </label>
            <input
              id={`query-term-${term.id}`}
              className="form-control"
              type="text"
              value={term.text}
              placeholder="Word, phrase, wildcard, or exclusion"
              onChange={(event) =>
                onChange(term.id, { text: event.target.value })
              }
            />
          </div>

          <div className="col-6 col-md-3 col-xl-2">
            <label
              className="form-label advanced-search-label"
              htmlFor={`query-operator-${term.id}`}
            >
              {index === 0 ? "Join" : "Operator"}
            </label>
            <select
              id={`query-operator-${term.id}`}
              className="form-select"
              value={term.operator}
              onChange={(event) =>
                onChange(term.id, {
                  operator: event.target.value as QueryTerm["operator"],
                })
              }
              disabled={index === 0}
            >
              {QUERY_OPERATOR_OPTIONS.map((operator) => (
                <option key={operator} value={operator}>
                  {operator}
                </option>
              ))}
            </select>
          </div>

          <div className="col-6 col-md-3 col-xl-2">
            <label
              className="form-label advanced-search-label"
              htmlFor={`query-field-${term.id}`}
            >
              Field
            </label>
            <select
              id={`query-field-${term.id}`}
              className="form-select"
              value={term.field}
              onChange={(event) =>
                onChange(term.id, {
                  field: event.target.value as QueryTerm["field"],
                })
              }
            >
              {QUERY_FIELD_OPTIONS.map((fieldOption) => (
                <option key={fieldOption.value} value={fieldOption.value}>
                  {fieldOption.label}
                </option>
              ))}
            </select>
          </div>

          <div className="col-6 col-md-2 col-xl-1">
            <div className="form-check advanced-search-check">
              <input
                id={`query-fuzzy-${term.id}`}
                className="form-check-input"
                type="checkbox"
                checked={term.fuzzy}
                disabled={fuzzyDisabled}
                onChange={(event) =>
                  onChange(term.id, { fuzzy: event.target.checked })
                }
              />
              <label
                className="form-check-label advanced-search-label"
                htmlFor={`query-fuzzy-${term.id}`}
              >
                Fuzzy
              </label>
            </div>
          </div>

          <div className="col-6 col-md-2 col-xl-1">
            <div className="form-check advanced-search-check">
              <input
                id={`query-phrase-${term.id}`}
                className="form-check-input"
                type="checkbox"
                checked={term.phrase}
                onChange={(event) =>
                  onChange(term.id, {
                    phrase: event.target.checked,
                    fuzzy: event.target.checked ? false : term.fuzzy,
                  })
                }
              />
              <label
                className="form-check-label advanced-search-label"
                htmlFor={`query-phrase-${term.id}`}
              >
                Phrase
              </label>
            </div>
          </div>

          <div className="col-12 col-md-2 col-xl-2 d-grid d-xl-flex justify-content-xl-end">
            <button
              type="button"
              className="btn btn-outline-danger"
              onClick={() => onRemove(term.id)}
              disabled={!canRemove}
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default QueryTermRow;
