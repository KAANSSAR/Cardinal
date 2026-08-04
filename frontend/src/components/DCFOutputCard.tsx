import type { DCFResponse } from "../lib/api";

function fmt(v: number | null | undefined, prefix = "$", suffix = "", decimals = 2): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${prefix}${(v / 1e12).toFixed(1)}T${suffix}`;
  if (abs >= 1e9) return `${prefix}${(v / 1e9).toFixed(0)}B${suffix}`;
  if (abs >= 1e6) return `${prefix}${(v / 1e6).toFixed(0)}M${suffix}`;
  return `${prefix}${v.toFixed(decimals)}${suffix}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function fmtPrice(price: number, currency: string): string {
  const sym = currency === "GBP" ? "£" : currency === "EUR" ? "€" : currency === "INR" ? "₹" : "$";
  return `${sym}${price.toFixed(2)}`;
}

export default function DCFOutputCard({ data }: { data: DCFResponse }) {
  const isNonUSD = data.currency && data.currency !== "USD";
  const currSym = data.currency === "GBP" ? "£" : data.currency === "EUR" ? "€" : data.currency === "INR" ? "₹" : "$";

  return (
    <div className="rounded-lg border border-term-border bg-term-panel p-5 space-y-5">
      <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest">
        DCF Valuation Output
        {data.exchange && <span className="ml-2 text-term-text-dim">{data.exchange}</span>}
        {data.currency && data.currency !== "USD" && (
          <span className="ml-2 px-1.5 py-0.5 rounded bg-term-accent/10 text-term-accent border border-term-accent/30 text-[10px]">
            {data.currency}
          </span>
        )}
      </p>

      {/* Partial data warning */}
      {data.is_partial && (
        <div className="rounded-lg bg-term-danger/10 border border-term-danger/30 px-4 py-3">
          <p className="text-sm font-medium text-term-danger">Partial data — DCF unavailable</p>
          <p className="text-xs text-term-text-dim mt-0.5">{data.partial_reason}</p>
          <p className="text-xs text-term-text-faint mt-1">
            Showing available market data. The DCF requires free cash flow and shares outstanding.
          </p>
        </div>
      )}

      {/* Intrinsic vs current price bar — only when full DCF available */}
      {!data.is_partial && data.intrinsic_value_per_share != null && (
        <div>
          <div className="flex justify-between text-xs font-mono text-term-text-faint mb-2 uppercase tracking-wide">
            <span>Intrinsic value</span>
            <span>Current price</span>
          </div>
          <div className="relative h-8 bg-term-panel-alt rounded-lg overflow-hidden border border-term-border-faint">
            {(() => {
              const intrinsic = data.intrinsic_value_per_share!;
              const current = data.current_price;
              const max = Math.max(intrinsic, current) * 1.1;
              const intrinsicPct = Math.min((intrinsic / max) * 100, 100);
              const currentPct = Math.min((current / max) * 100, 100);
              const overvalued = current > intrinsic;
              return (
                <>
                  <div className="absolute top-0 left-0 h-full bg-term-accent/15 rounded-lg transition-all"
                    style={{ width: `${intrinsicPct}%` }} />
                  <div className={`absolute top-1 h-6 w-0.5 rounded ${overvalued ? "bg-term-danger" : "bg-term-accent-2"}`}
                    style={{ left: `${currentPct}%` }} />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`font-mono text-xs font-semibold ${overvalued ? "text-term-danger" : "text-term-accent-2"}`}>
                      {data.premium_discount_pct != null
                        ? `${data.premium_discount_pct > 0 ? "▲" : "▼"} ${Math.abs(data.premium_discount_pct * 100).toFixed(1)}% ${overvalued ? "overvalued" : "undervalued"}`
                        : "—"}
                    </span>
                  </div>
                </>
              );
            })()}
          </div>
          <div className="flex justify-between text-xs font-mono mt-1">
            <span className="text-term-accent">{fmtPrice(data.intrinsic_value_per_share!, data.currency)}</span>
            <span className={data.premium_discount_pct != null && data.premium_discount_pct > 0 ? "text-term-danger" : "text-term-accent-2"}>
              {fmtPrice(data.current_price, data.currency)}
            </span>
          </div>
        </div>
      )}

      {/* Current price — always shown */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div>
          <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Current price ({data.currency})</p>
          <p className="font-mono font-semibold text-term-text">
            {currSym}{data.current_price.toFixed(2)}
          </p>
          {isNonUSD && data.current_price_usd != null && (
            <p className="text-[11px] text-term-text-dim font-mono">≈ ${data.current_price_usd.toFixed(2)} USD</p>
          )}
        </div>

        {!data.is_partial && data.intrinsic_value_per_share != null && (
          <div>
            <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Intrinsic value ({data.currency})</p>
            <p className="font-mono font-semibold text-term-accent">
              {currSym}{data.intrinsic_value_per_share.toFixed(2)}
            </p>
            {isNonUSD && data.usd_conversion_rate != null && (
              <p className="text-[11px] text-term-text-dim font-mono">
                ≈ ${(data.intrinsic_value_per_share * data.usd_conversion_rate).toFixed(2)} USD
              </p>
            )}
          </div>
        )}

        {!data.is_partial && (
          <>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">WACC</p>
              <p className="font-mono font-semibold text-term-text">{fmtPct(data.wacc)}</p>
            </div>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Cost of equity</p>
              <p className="font-mono font-semibold text-term-text">{fmtPct(data.cost_of_equity)}</p>
            </div>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">TV % of EV</p>
              <p className="font-mono font-semibold text-term-text">{fmtPct(data.terminal_value_pct_of_ev)}</p>
            </div>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Enterprise value</p>
              <p className="font-mono font-semibold text-term-text">{fmt(data.enterprise_value, currSym)}</p>
            </div>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Equity value</p>
              <p className="font-mono font-semibold text-term-text">{fmt(data.equity_value, currSym)}</p>
            </div>
            <div>
              <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">PV terminal value</p>
              <p className="font-mono font-semibold text-term-text">{fmt(data.pv_terminal_value, currSym)}</p>
            </div>
          </>
        )}
      </div>

      {/* Projected FCF strip */}
      {!data.is_partial && data.pv_projected_fcf.length > 0 && (
        <div>
          <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide mb-2">Projected FCF (PV)</p>
          <div className="flex gap-2 flex-wrap">
            {data.pv_projected_fcf.map((v, i) => (
              <div key={i} className="text-center bg-term-panel-alt rounded px-2.5 py-1.5 border border-term-border-faint">
                <p className="text-[10px] font-mono text-term-text-faint">Y{i + 1}</p>
                <p className="font-mono text-xs text-term-text">{fmt(v, currSym)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* USD conversion note */}
      {isNonUSD && data.usd_conversion_rate != null && (
        <p className="text-[10px] font-mono text-term-text-faint border-t border-term-border-faint pt-3">
          Live FX: 1 {data.currency} = ${data.usd_conversion_rate.toFixed(4)} USD
        </p>
      )}
    </div>
  );
}