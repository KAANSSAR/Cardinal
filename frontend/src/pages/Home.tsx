import TickerSearch from "../components/TickerSearch";
import MarketIndices from "../components/MarketIndices";
import GainersLosers from "../components/GainersLosers";
import SectorHeatmap from "../components/SectorHeatmap";

// Lens identity colors are fixed regardless of the Amber/Cyan/Green terminal
// theme — these code "which lens" not "which terminal skin", so they stay
// constant even as the surrounding chrome re-themes.
const LENSES = [
  { label: "Fundamental", dot: "#0d9488" },
  { label: "Quant", dot: "#3b82f6" },
  { label: "Backtest", dot: "#a78bfa" },
  { label: "AI Agents", dot: "#f59e0b" },
];

const QUICK_TICKERS = ["AAPL", "MSFT", "RELIANCE.NS", "SAP.DE"];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16 space-y-16">
      {/* Hero */}
      <div className="text-center max-w-2xl mx-auto">
        <p className="font-mono text-xs tracking-widest text-term-accent uppercase mb-3">
          Multi-lens equity analysis
        </p>
        <h1 className="font-display text-5xl font-semibold text-term-text leading-tight mb-4">
          One ticker. Four lenses.
        </h1>
        <p className="text-term-text-dim text-lg mb-8">
          Fundamental valuation, quant signals, algo backtesting, and AI interpretation —
          for any equity across US, Indian, and European markets.
        </p>

        <TickerSearch size="large" />

        <div className="flex flex-wrap justify-center gap-2 mt-3">
          <span className="text-xs font-mono text-term-text-faint">Try:</span>
          {QUICK_TICKERS.map((ticker) => (
            <a
              key={ticker}
              href={`/ticker/${ticker}`}
              className="text-xs font-mono text-term-accent hover:underline"
            >
              {ticker}
            </a>
          ))}
        </div>

        <div className="flex flex-wrap justify-center gap-5 mt-10">
          {LENSES.map((lens) => (
            <div key={lens.label} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: lens.dot }} />
              <span className="font-mono text-xs text-term-text-dim uppercase tracking-wide">
                {lens.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Market indices */}
      <MarketIndices />

      {/* Gainers/Losers + Sector Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        <GainersLosers />
        <SectorHeatmap />
      </div>
    </div>
  );
}