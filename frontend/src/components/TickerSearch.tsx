import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

interface TickerSearchProps {
  size?: "large" | "default";
}

export default function TickerSearch({ size = "default" }: TickerSearchProps) {
  const [value, setValue] = useState("");
  const navigate = useNavigate();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (ticker.length === 0) return;
    navigate(`/ticker/${ticker}`);
  }

  const inputClasses =
    size === "large"
      ? "w-full rounded-xl border border-slate-300 bg-white px-5 py-4 text-lg font-mono tracking-wide shadow-sm focus:border-teal"
      : "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono shadow-sm focus:border-teal";

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="AAPL, RELIANCE.NS, SAP.DE…"
        aria-label="Ticker symbol"
        className={inputClasses}
      />
      <button
        type="submit"
        className="shrink-0 rounded-lg bg-navy px-5 py-2 text-sm font-medium text-white hover:bg-navy-2 transition-colors"
      >
        Analyze
      </button>
    </form>
  );
}
