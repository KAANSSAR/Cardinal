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
  if (value == null) return <span className="text-slate-light">—</span>;
  const diff = median != null ? (value - median) / median : null;
  const color =
    diff == null ? "text-dark-text"
    : diff > 0.1 ? "text-red-500"
    : diff < -0.1 ? "text-green-600"
    : "text-dark-text";
  return <span className={`font-mono ${color}`}>{value.toFixed(1)}×</span>;
}

export default function CompsTable({ data }: { data: CompsResponse }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide mb-4">
        Comparable companies
      </p>

      {data.peers.length === 0 ? (
        <p className="text-sm text-slate-light text-center py-4">
          No peer data available for this ticker.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-dark">
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
                    className="border-b border-slate-50 hover:bg-slate-50 transition-colors group"
                  >
                    <td className="py-2.5 pr-4">
                      <Link
                        to={`/ticker/${peer.ticker}`}
                        className="flex flex-col gap-0.5 w-fit"
                      >
                        <span className="font-mono text-xs font-semibold text-teal group-hover:underline">
                          {peer.ticker}
                        </span>
                        <span className="text-[11px] text-slate-light truncate max-w-[120px]">
                          {peer.name}
                        </span>
                      </Link>
                    </td>
                    <td className="text-right py-2.5 px-2 font-mono text-xs text-dark-text">
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
                <tr className="border-t-2 border-slate-200 bg-slate-50">
                  <td className="py-2.5 pr-4 text-[11px] font-semibold text-slate uppercase tracking-wide">
                    Peer median
                  </td>
                  <td className="text-right py-2.5 px-2 text-slate text-xs">—</td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-teal">
                    {fmt(data.median_ev_ebitda)}
                  </td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-teal">
                    {fmt(data.median_pe)}
                  </td>
                  <td className="text-right py-2.5 px-2 font-mono text-sm font-semibold text-teal">
                    {fmt(data.median_ev_revenue)}
                  </td>
                  <td className="text-right py-2.5 pl-2 font-mono text-sm font-semibold text-teal">
                    {fmt(data.median_ps)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Implied EV callouts */}
          {(data.implied_ev_from_ebitda != null || data.implied_ev_from_revenue != null) && (
            <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 gap-4">
              {data.implied_ev_from_ebitda != null && (
                <div>
                  <p className="text-[11px] text-slate-light">Comps-implied EV (EV/EBITDA)</p>
                  <p className="font-mono text-sm font-semibold text-dark-text">
                    {fmtCap(data.implied_ev_from_ebitda)}
                  </p>
                </div>
              )}
              {data.implied_ev_from_revenue != null && (
                <div>
                  <p className="text-[11px] text-slate-light">Comps-implied EV (EV/Revenue)</p>
                  <p className="font-mono text-sm font-semibold text-dark-text">
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