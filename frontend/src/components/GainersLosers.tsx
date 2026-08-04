import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMarketMovers, type MoverQuote } from "../lib/api";
import Sparkline from "./Sparkline";

function MoverRow({ mover, positive }: { mover: MoverQuote; positive: boolean }) {
  const navigate = useNavigate();
  const color = positive ? "text-term-accent-2" : "text-term-danger";
  return (
    <button
      onClick={() => navigate(`/ticker/${mover.ticker}`)}
      className="w-full flex items-center gap-3 py-2 hover:bg-term-panel-alt transition-colors rounded px-1.5 -mx-1.5"
    >
      <span className="font-mono text-xs font-semibold text-term-text w-14 text-left shrink-0">
        {mover.ticker}
      </span>
      <Sparkline
        data={mover.sparkline.map((p) => p.value)}
        width={64}
        height={22}
        strokeColor={positive ? "var(--color-term-accent-2)" : "var(--color-term-danger)"}
        strokeWidth={1.5}
        className="shrink-0"
      />
      <span className={`font-mono text-xs font-medium ml-auto ${color}`}>
        {positive ? "+" : ""}
        {(mover.change_pct * 100).toFixed(1)}%
      </span>
    </button>
  );
}

export default function GainersLosers() {
  const [gainers, setGainers] = useState<MoverQuote[] | null>(null);
  const [losers, setLosers] = useState<MoverQuote[] | null>(null);

  useEffect(() => {
    fetchMarketMovers(5)
      .then((data) => {
        setGainers(data.gainers);
        setLosers(data.losers);
      })
      .catch(() => {
        setGainers([]);
        setLosers([]);
      });
  }, []);

  return (
    <div className="rounded-lg border border-term-border bg-term-panel p-5 h-full">
      <p className="font-mono text-[10px] text-term-text-faint uppercase tracking-widest mb-4">
        Gainers &amp; Losers
      </p>
      <div className="grid grid-cols-2 gap-6">
        <div>
          <p className="font-mono text-[10px] text-term-text-faint uppercase tracking-widest mb-1.5">
            Gainers
          </p>
          {gainers === null && <div className="h-40 animate-pulse bg-term-panel-alt rounded" />}
          {gainers?.map((m) => <MoverRow key={m.ticker} mover={m} positive />)}
        </div>
        <div>
          <p className="font-mono text-[10px] text-term-text-faint uppercase tracking-widest mb-1.5">
            Losers
          </p>
          {losers === null && <div className="h-40 animate-pulse bg-term-panel-alt rounded" />}
          {losers?.map((m) => <MoverRow key={m.ticker} mover={m} positive={false} />)}
        </div>
      </div>
    </div>
  );
}