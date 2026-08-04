import { useEffect, useState } from "react";
import { fetchTickerTape, type TapeQuote } from "../lib/api";

const REFRESH_INTERVAL_MS = 60_000; // matches backend 60s cache TTL

export default function TickerTape() {
  const [quotes, setQuotes] = useState<TapeQuote[]>([]);

  useEffect(() => {
    let cancelled = false;

    function load() {
      fetchTickerTape()
        .then((data) => {
          if (!cancelled) setQuotes(data.quotes);
        })
        .catch(() => {
          /* tape is decorative-adjacent; fail silently rather than block the page */
        });
    }

    load();
    const interval = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (quotes.length === 0) return null;

  // Duplicate the list so the CSS marquee (translateX(-50%)) loops seamlessly
  const items = [...quotes, ...quotes];

  return (
    <div className="w-full overflow-hidden border-b border-term-border-faint bg-term-bg-alt">
      <div className="flex w-max animate-marquee py-2">
        {items.map((q, i) => (
          <div
            key={`${q.ticker}-${i}`}
            className="flex items-center gap-2 px-5 font-mono text-xs whitespace-nowrap shrink-0"
          >
            <span className="text-term-text font-medium">{q.ticker}</span>
            <span className="text-term-text-dim">{q.price.toFixed(2)}</span>
            <span className={q.change_pct >= 0 ? "text-term-accent-2" : "text-term-danger"}>
              {q.change_pct >= 0 ? "+" : ""}
              {(q.change_pct * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}