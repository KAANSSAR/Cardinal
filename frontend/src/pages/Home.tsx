import TickerSearch from "../components/TickerSearch";

const LENSES = [
  { label: "Fundamental", desc: "Live DCF valuation with editable WACC, growth, and terminal value assumptions.", color: "border-teal text-teal" },
  { label: "Quant", desc: "Momentum, rolling Sharpe, beta, and volatility signals across timeframes.", color: "border-blue text-blue" },
  { label: "Backtest", desc: "Run momentum and mean-reversion strategies against historical price data.", color: "border-purple text-purple" },
  { label: "AI Agents", desc: "Xavi, Iniesta, Busquets, and Messi interpret each lens — read-only, grounded.", color: "border-amber text-amber-dark" },
];

const QUICK_TICKERS = ["AAPL", "MSFT", "RELIANCE.NS", "SAP.DE"];

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-20">
      <p className="font-mono text-xs tracking-widest text-teal uppercase mb-3">
        Multi-lens equity analysis
      </p>
      <h1 className="font-display text-5xl font-semibold text-dark-text leading-tight mb-4">
        One ticker. Four lenses.
      </h1>
      <p className="text-slate text-lg mb-10 max-w-xl">
        Fundamental valuation, quant signals, algo backtesting, and AI interpretation —
        for any equity across US, Indian, and European markets.
      </p>

      <TickerSearch size="large" />

      <div className="flex flex-wrap gap-2 mt-3">
        <span className="text-xs text-slate-light">Try:</span>
        {QUICK_TICKERS.map((ticker) => (
          <a
            key={ticker}
            href={`/ticker/${ticker}`}
            className="text-xs font-mono text-teal hover:underline"
          >
            {ticker}
          </a>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-16">
        {LENSES.map((lens) => (
          <div
            key={lens.label}
            className={`border-l-2 ${lens.color} pl-4 py-1`}
          >
            <p className={`font-semibold text-sm ${lens.color}`}>{lens.label}</p>
            <p className="text-sm text-slate-dark mt-1">{lens.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
