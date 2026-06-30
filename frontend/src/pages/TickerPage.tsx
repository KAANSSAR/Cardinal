import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, fetchDCF, type DCFResponse } from "../lib/api";

const TABS = [
  { key: "fundamental", label: "Fundamental", color: "border-teal text-teal", active: true },
  { key: "quant", label: "Quant", color: "border-blue text-blue", active: false },
  { key: "backtest", label: "Backtest", color: "border-purple text-purple", active: false },
];

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toFixed(2)}`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [data, setData] = useState<DCFResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    fetchDCF(symbol)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
        else setError("Something went wrong fetching this ticker.");
      })
      .finally(() => setLoading(false));
  }, [symbol]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold text-dark-text">
            {data?.company_name ?? symbol}
          </h1>
          <p className="font-mono text-sm text-slate">{symbol}</p>
        </div>
        {data && (
          <div className="text-right">
            <p className="font-mono text-2xl font-semibold text-dark-text">
              ${data.current_price.toFixed(2)}
            </p>
            <p
              className={`text-sm font-medium ${
                data.premium_discount_pct > 0 ? "text-red-600" : "text-green-600"
              }`}
            >
              {data.premium_discount_pct > 0 ? "+" : ""}
              {formatPct(data.premium_discount_pct)} vs intrinsic
            </p>
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-8">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            disabled={!tab.active}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab.active
                ? tab.color
                : "border-transparent text-slate-light cursor-not-allowed"
            }`}
            title={tab.active ? undefined : "Coming soon"}
          >
            {tab.label}
            {!tab.active && <span className="ml-1.5 text-[10px] align-top">soon</span>}
          </button>
        ))}
      </div>

      {loading && <p className="text-slate">Running DCF valuation…</p>}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {data && !loading && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="font-mono text-xs text-slate-light uppercase tracking-wide mb-4">
            DCF Output — base case assumptions
          </p>
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            {[
              ["WACC", formatPct(data.wacc)],
              ["Cost of Equity", formatPct(data.cost_of_equity)],
              ["PV of Projected FCF", formatCurrency(data.pv_projected_fcf.reduce((a, b) => a + b, 0))],
              ["PV of Terminal Value", formatCurrency(data.pv_terminal_value)],
              ["Terminal Value % of EV", formatPct(data.terminal_value_pct_of_ev)],
              ["Enterprise Value", formatCurrency(data.enterprise_value)],
              ["Equity Value", formatCurrency(data.equity_value)],
              ["Intrinsic Value / Share", `$${data.intrinsic_value_per_share.toFixed(2)}`],
            ].map(([label, value]) => (
              <div key={label} className="flex flex-col">
                <dt className="text-slate-light text-xs">{label}</dt>
                <dd className="font-mono font-medium text-dark-text">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-slate-light mt-6 border-t border-slate-100 pt-4">
            Editable assumption sliders (WACC, growth rate, projection years) and
            comparable companies land in the next build pass.
          </p>
        </div>
      )}
    </div>
  );
}
