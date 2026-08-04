import { Link } from "react-router-dom";
import type { CompsResponse } from "../lib/api";

function fmt(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(1)}×`;
}

function fmtCap(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(0)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
}

function Cell({ value, median }: { value: number | null; median: number | null }) {
  if (value == null) return <span className="text-term-text-faint">—</span>;
  const diff = median != null ? (value - median) / median : null;
  const color =
    diff == null ? "text-term-text"
    : diff > 0.1 ? "text-term-danger"
    : diff < -0.1 ? "text-term-accent-2"
    : "text-term-text";
  return <span className={`font-mono ${color}`}>{value.toFixed(1)}×</span>;
}

export default function CompsTable({ data }: { data: CompsResponse }) {
  return (
    <div className="rounded-lg border border-term-border bg-term-panel p-5">
      <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest mb-4">
        Comparable companies
      </p>

      {data.peers.length === 0 ? (
        <p className="text-sm text-term-text-faint text-center py-4">
          No peer data available for this ticker.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-term-border-faint text-[11px] font-mono uppercase tracking-wide text-term-text-faint">
                  <th className="text-left py-2.5 pr-4 font-medium">Company</th>
                  <th className="text-right py-2.5 px-2 font-medium">Mkt Cap</th>
                  <th className="text-right py-2.5 px-2 font-medium">EV/EBITDA</th>
                  <th className="text-right py-2.5 px-2 font-medium">P/E</th>
                  <th className="text-right py-2.5 px-2 font-medium">EV/Rev</th>
                  <th className="text-right py-2.5 pl-2 font-medium">P/S</th>
                </tr>
              </thead>
              <tbody>
                {data.peers.map((peer) => (
                  <tr
                    key={peer.ticker}
                    className="border-b border-term-border-faint hover:bg-term-panel-alt transition-colors group"
                  >
                    <td className="py-2.5 pr-4">
                      <Link
                        to={`/ticker/${peer.ticker}`}
                        className="flex flex-col gap-0.5 w-fit"
                      >
                        <span className="font-mono text-xs font-semibold text-term-accent group-hover:underline">
                          {peer.ticker}
                        </span>
                        <span className="text-[11px] text-term-text-faint truncate max-w-[120px]">
                          {peer.name}
                        </span>
                      </Link>
                    </td>
                    <td className="text-right py-2.5 px-2 font-mono text-xs text-term-text-dim">
                      {fmtCap(peer.market_cap)}
                    </td>
                    <td className="text-right py-2.5 px-2">
                      <Cell value={peer.ev_ebitda} median={data.median_ev_ebitda} />
                    </td>
                    <td className="text-right py-2.5 px-2">
                      <Cell value={peer.pe_ratio} median={data.median_pe} />
                    </td>
                    <td className="text-right py-2.5 px-2">
                      <Cell value={peer.ev_revenue} median={data.median_ev_revenue} />
                    </td>
                    <td className="text-right py-2.5 pl-2">
                      <Cell value={peer.ps_ratio} median={data.median_ps} />
                    </td>
                  </tr>
                ))}

                {/* Median row */}
                <tr className="border-t-2 border-term-border bg-term-panel-alt">
                  <td className="py-2.5 pr-4 text-[11px] font-mono font-semibold text-term-text-dim uppercase tracking-wide">
                    Peer median
                  </td>
                  <td className="text-right py-2.5 px-2 text-term-text-faint text-xs">—</td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-term-accent">
                    {fmt(data.median_ev_ebitda)}
                  </td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-term-accent">
                    {fmt(data.median_pe)}
                  </td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-term-accent">
                    {fmt(data.median_ev_revenue)}
                  </td>
                  <td className="text-right py-2.5 pl-2 font-mono text-sm font-semibold text-term-accent">
                    {fmt(data.median_ps)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Implied EV callouts */}
          {(data.implied_ev_from_ebitda != null || data.implied_ev_from_revenue != null) && (
            <div className="mt-4 pt-4 border-t border-term-border-faint grid grid-cols-2 gap-4">
              {data.implied_ev_from_ebitda != null && (
                <div>
                  <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Comps-implied EV (EV/EBITDA)</p>
                  <p className="font-mono text-sm font-semibold text-term-text">
                    {fmtCap(data.implied_ev_from_ebitda)}
                  </p>
                </div>
              )}
              {data.implied_ev_from_revenue != null && (
                <div>
                  <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">Comps-implied EV (EV/Revenue)</p>
                  <p className="font-mono text-sm font-semibold text-term-text">
                    {fmtCap(data.implied_ev_from_revenue)}
                  </p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}