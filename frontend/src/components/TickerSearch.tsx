import { useState, useRef, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { searchTickers, type SearchResult } from "../lib/api";
import { useDebounce } from "../lib/useDebounce";

interface Props {
  size?: "large" | "default";
}

export default function TickerSearch({ size = "default" }: Props) {
  const [value, setValue] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const debouncedValue = useDebounce(value, 300);

  // Fetch suggestions when debounced value changes
  useEffect(() => {
    if (debouncedValue.trim().length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    searchTickers(debouncedValue.trim())
      .then((data) => {
        setResults(data.results);
        setOpen(data.results.length > 0);
        setActiveIndex(-1);
      })
      .catch(() => {
        setResults([]);
        setOpen(false);
      })
      .finally(() => setLoading(false));
  }, [debouncedValue]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(result: SearchResult) {
    setValue(result.symbol);
    setOpen(false);
    navigate(`/ticker/${result.symbol}`);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (!ticker) return;
    setOpen(false);
    // If user typed a company name and we have a result, use that symbol
    if (results.length > 0 && activeIndex >= 0) {
      navigate(`/ticker/${results[activeIndex].symbol}`);
    } else if (results.length > 0 && !ticker.includes(" ")) {
      // Direct ticker — navigate as-is
      navigate(`/ticker/${ticker}`);
    } else if (results.length > 0) {
      // They typed a name, use first result
      navigate(`/ticker/${results[0].symbol}`);
    } else {
      navigate(`/ticker/${ticker}`);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      handleSelect(results[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const isLarge = size === "large";

  return (
    <div ref={containerRef} className="relative w-full">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => { setValue(e.target.value); setOpen(true); }}
            onKeyDown={handleKeyDown}
            onFocus={() => results.length > 0 && setOpen(true)}
            placeholder="AAPL, Apple, Reliance, SAP…"
            aria-label="Search by ticker or company name"
            autoComplete="off"
            className={`w-full rounded-xl border border-slate-300 bg-white font-mono tracking-wide shadow-sm focus:border-teal focus:outline-none transition-colors ${
              isLarge ? "px-5 py-4 text-lg" : "px-3 py-2 text-sm"
            }`}
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="h-4 w-4 rounded-full border-2 border-teal border-t-transparent animate-spin" />
            </div>
          )}
        </div>
        <button
          type="submit"
          className={`shrink-0 rounded-xl bg-navy font-medium text-white hover:bg-navy-2 transition-colors ${
            isLarge ? "px-6 py-4 text-base" : "px-5 py-2 text-sm"
          }`}
        >
          Analyze
        </button>
      </form>

      {/* Dropdown */}
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1.5 z-50 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden">
          {results.map((result, i) => (
            <button
              key={result.symbol}
              onMouseDown={() => handleSelect(result)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                i === activeIndex ? "bg-slate-50" : "hover:bg-slate-50"
              }`}
            >
              <span className="font-mono text-sm font-semibold text-dark-text w-20 shrink-0">
                {result.symbol}
              </span>
              <span className="text-sm text-slate truncate flex-1">{result.name}</span>
              {result.exchange && (
                <span className="text-[11px] text-slate-light shrink-0">{result.exchange}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}