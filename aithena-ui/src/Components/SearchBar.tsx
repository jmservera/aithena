import { useState, FormEvent } from "react";

interface SearchBarProps {
  onSearch: (query: string) => void;
  loading?: boolean;
  initialQuery?: string;
}

const SearchBar = ({ onSearch, loading = false, initialQuery = "" }: SearchBarProps) => {
  const [input, setInput] = useState(initialQuery);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (trimmed) {
      onSearch(trimmed);
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit} role="search">
      <input
        type="search"
        className="search-input"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Search the library…"
        aria-label="Search query"
        disabled={loading}
      />
      <button
        type="submit"
        className="search-button"
        disabled={loading || !input.trim()}
        aria-label="Search"
      >
        {loading ? "Searching…" : "Search"}
      </button>
    </form>
  );
};

export default SearchBar;
