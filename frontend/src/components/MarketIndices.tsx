import { useEffect, useState } from "react";
import { fetchMarketIndices, type IndexQuote } from "../lib/api";
import Sparkline from "./Sparkline";

export default function MarketIndices() {
  const [indices, setIndices] = useState<IndexQuote[] | null>(null);

  useEffect(() => {
    fetchMarketIndices()
      .then((data) => setIndices(data.indices))
      .catch(() => setIndices([]));
  }, []);

  if (indices === null) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-lg border border-term-border bg-term-panel p-5 h-[132px] animate-pulse" />
        ))}
      </div>
    );
  }

  if (indices.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {indices.map((idx) => {
        const positive = idx.change_pct >= 0;
        const color = positive ? "text-term-accent-2" : "text-term-danger";
        return (
          <div key={idx.symbol} className="rounded-lg border border-term-border bg-term-panel p-5">
            <p className="font-mono text-[10px] text-term-text-faint uppercase tracking-widest mb-1">
              {idx.name}
            </p>
            <p className="font-mono text-2xl font-semibold text-term-text mb-1 tabular-nums">
              {idx.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
            <p className={`font-mono text-xs font-medium mb-3 ${color}`}>
              {positive ? "+" : ""}
              {(idx.change_pct * 100).toFixed(2)}%
            </p>
            <Sparkline
              data={idx.sparkline.map((p) => p.value)}
              width={220}
              height={44}
              strokeColor={positive ? "var(--color-term-accent-2)" : "var(--color-term-danger)"}
              className="w-full"
            />
          </div>
        );
      })}
    </div>
  );
}