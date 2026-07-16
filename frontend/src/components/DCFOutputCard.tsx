import type { DCFResponse } from "../lib/api";

function fmtB(v: number): string {
  if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

export default function DCFOutputCard({ data }: { data: DCFResponse }) {
  const isOvervalued = data.premium_discount_pct > 0;
  const lo = Math.min(data.intrinsic_value_per_share, data.current_price) * 0.85;
  const hi = Math.max(data.intrinsic_value_per_share, data.current_price) * 1.15;
  const range = hi - lo;
  const intrinsicPct = range > 0 ? ((data.intrinsic_value_per_share - lo) / range) * 100 : 50;
  const currentPct = range > 0 ? ((data.current_price - lo) / range) * 100 : 50;

  const metrics: [string, string][] = [
    ["WACC", fmtPct(data.wacc)],
    ["Cost of equity", fmtPct(data.cost_of_equity)],
    ["TV % of EV", fmtPct(data.terminal_value_pct_of_ev)],
    ["PV projected FCF", fmtB(data.pv_projected_fcf.reduce((a, b) => a + b, 0))],
    ["PV terminal value", fmtB(data.pv_terminal_value)],
    ["Enterprise value", fmtB(data.enterprise_value)],
    ["Equity value", fmtB(data.equity_value)],
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide mb-4">DCF valuation output</p>

      <div className="mb-5 p-4 rounded-lg bg-slate-50 border border-slate-100">
        <div className="flex justify-between items-end mb-3">
          <div>
            <p className="text-[11px] text-slate-light uppercase tracking-wide mb-0.5">Intrinsic value</p>
            <p className="font-mono text-2xl font-semibold text-dark-text">${data.intrinsic_value_per_share.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-[11px] text-slate-light uppercase tracking-wide mb-0.5">Current price</p>
            <p className="font-mono text-2xl font-semibold text-dark-text">${data.current_price.toFixed(2)}</p>
          </div>
        </div>
        <div className="relative h-4 bg-slate-200 rounded-full">
          <div className="absolute top-0 bottom-0 w-0.5 bg-teal rounded-full" style={{ left: `${intrinsicPct}%` }} />
          <div className={`absolute top-0 bottom-0 w-0.5 rounded-full ${isOvervalued ? "bg-red-400" : "bg-green-500"}`} style={{ left: `${currentPct}%` }} />
        </div>
        <div className="flex justify-between mt-1.5 text-[10px]">
          <span className="text-teal">— intrinsic</span>
          <span className={`font-semibold ${isOvervalued ? "text-red-500" : "text-green-600"}`}>
            {isOvervalued ? "▲" : "▼"} {fmtPct(Math.abs(data.premium_discount_pct))} {isOvervalued ? "overvalued" : "undervalued"}
          </span>
          <span className={isOvervalued ? "text-red-400" : "text-green-500"}>— current</span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2.5">
        {metrics.map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <dt className="text-[11px] text-slate-light">{label}</dt>
            <dd className="font-mono text-sm font-medium text-dark-text">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 pt-4 border-t border-slate-100">
        <p className="text-[11px] text-slate-light uppercase tracking-wide mb-2">Projected FCF (PV)</p>
        <div className="flex gap-2">
          {data.pv_projected_fcf.map((pv, i) => (
            <div key={i} className="flex-1 text-center">
              <p className="text-[10px] text-slate-light">Y{i + 1}</p>
              <p className="font-mono text-xs font-medium text-dark-text">{fmtB(pv)}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}