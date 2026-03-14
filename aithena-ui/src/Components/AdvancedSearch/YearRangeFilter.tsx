import { YearRange } from "./buildQuery";

interface YearRangeFilterProps {
  value: YearRange;
  onChange: (nextRange: YearRange) => void;
}

function YearRangeFilter({ value, onChange }: YearRangeFilterProps) {
  return (
    <div>
      <div className="advanced-search-section-label">Year range</div>
      <div className="row g-3">
        <div className="col-6">
          <label
            className="form-label advanced-search-label"
            htmlFor="year-range-from"
          >
            From
          </label>
          <input
            id="year-range-from"
            className="form-control"
            type="number"
            inputMode="numeric"
            step={1}
            placeholder="1900"
            value={value.from}
            onChange={(event) =>
              onChange({ ...value, from: event.target.value })
            }
          />
        </div>
        <div className="col-6">
          <label
            className="form-label advanced-search-label"
            htmlFor="year-range-to"
          >
            To
          </label>
          <input
            id="year-range-to"
            className="form-control"
            type="number"
            inputMode="numeric"
            step={1}
            placeholder="1950"
            value={value.to}
            onChange={(event) => onChange({ ...value, to: event.target.value })}
          />
        </div>
      </div>
    </div>
  );
}

export default YearRangeFilter;
