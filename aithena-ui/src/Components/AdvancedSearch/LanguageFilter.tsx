interface LanguageFilterProps {
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

const LANGUAGE_LABELS: Record<string, string> = {
  ca: "Catalan",
  en: "English",
  es: "Spanish",
  fr: "French",
};

function formatLanguageLabel(code: string) {
  const normalizedCode = code.trim().toLowerCase();
  return LANGUAGE_LABELS[normalizedCode]
    ? `${LANGUAGE_LABELS[normalizedCode]} (${normalizedCode})`
    : normalizedCode.toUpperCase();
}

function LanguageFilter({ value, options, onChange }: LanguageFilterProps) {
  return (
    <div>
      <label className="form-label advanced-search-section-label" htmlFor="language-filter">
        Language filter
      </label>
      <select
        id="language-filter"
        className="form-select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">All detected languages</option>
        {options.map((languageCode) => (
          <option key={languageCode} value={languageCode}>
            {formatLanguageLabel(languageCode)}
          </option>
        ))}
      </select>
    </div>
  );
}

export default LanguageFilter;
