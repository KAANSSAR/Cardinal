import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";
import type { BacktestResponse, BacktestStrategy } from "../lib/api";

interface Props {
  onRun: (strategy: BacktestStrategy, params: Record<string, number>) => void;
  data: BacktestResponse | null;
  loading: boolean;
}

function fmtPct(v: number | null): string {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(1)}%`;
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
      <p className="text-[11px] text-slate-light mb-1">{label}</p>
      <p className={`font-mono text-xl font-semibold ${color ?? "text-dark-text"}`}>{value}</p>
    </div>
  );
}

export default function BacktestView({ onRun, data, loading }: Props) {
  const [strategy, setStrategy] = useState<BacktestStrategy>("momentum");
  const [fastWindow, setFastWindow] = useState(50);
  const [slowWindow, setSlowWindow] = useState(200);
  const [lookback, setLookback] = useState(20);
  const [entryZ, setEntryZ] = useState(2.0);

  function handleRun() {
    const params: Record<string, number> = strategy === "momentum"
      ? { fast_window: fastWindow, slow_window: slowWindow }
      : { lookback: lookback, entry_z: entryZ };
    onRun(strategy, params);
  }

  const chartData = data
    ? data.pnl_curve.map((p, i) => ({
        date: p.date,
        strategy: parseFloat(((p.value - 1) * 100).toFixed(2)),
        buyHold: parseFloat((((data.buy_hold_curve[i]?.value ?? 1) - 1) * 100).toFixed(2)),
      }))
    : [];

  const strategyReturn = data ? data.total_return * 100 : null;
  const buyHoldReturn = data ? data.buy_hold_return * 100 : null;
  const outperformance = strategyReturn != null && buyHoldReturn != null ? strategyReturn - buyHoldReturn : null;

  return (
    <div className="space-y-6">
      {/* Strategy selector + params */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide mb-4">
          Strategy configuration
        </p>

        <div className="flex gap-2 mb-5">
          {(["momentum", "mean_reversion"] as BacktestStrategy[]).map((s) => (
            <button
              key={s}
              onClick={() => setStrategy(s)}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors border ${
                strategy === s
                  ? "bg-purple/10 border-purple text-purple"
                  : "border-slate-200 text-slate hover:bg-slate-50"
              }`}
            >
              {s === "momentum" ? "Momentum (Golden Cross)" : "Mean Reversion (σ)"}
            </button>
          ))}
        </div>

        {strategy === "momentum" ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-dark-text">Fast MA window</span>
                <span className="font-mono text-sm text-purple font-semibold">{fastWindow}d</span>
              </div>
              <input type="range" min={10} max={100} step={5} value={fastWindow}
                onChange={(e) => setFastWindow(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-slate-200 accent-purple cursor-pointer" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-dark-text">Slow MA window</span>
                <span className="font-mono text-sm text-purple font-semibold">{slowWindow}d</span>
              </div>
              <input type="range" min={50} max={300} step={10} value={slowWindow}
                onChange={(e) => setSlowWindow(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-slate-200 accent-purple cursor-pointer" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-dark-text">Lookback window</span>
                <span className="font-mono text-sm text-purple font-semibold">{lookback}d</span>
              </div>
              <input type="range" min={5} max={60} step={5} value={lookback}
                onChange={(e) => setLookback(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-slate-200 accent-purple cursor-pointer" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-dark-text">Entry threshold (σ)</span>
                <span className="font-mono text-sm text-purple font-semibold">{entryZ.toFixed(1)}σ</span>
              </div>
              <input type="range" min={1.0} max={3.0} step={0.25} value={entryZ}
                onChange={(e) => setEntryZ(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-slate-200 accent-purple cursor-pointer" />
            </div>
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={loading}
          className="mt-5 w-full py-2.5 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-2 transition-colors disabled:opacity-50"
        >
          {loading ? "Running backtest…" : `Run ${strategy === "momentum" ? "momentum" : "mean reversion"} backtest`}
        </button>
      </div>

      {/* Results */}
      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard
              label="Strategy return"
              value={fmtPct(data.total_return)}
              color={data.total_return >= 0 ? "text-green-600" : "text-red-500"}
            />
            <MetricCard
              label="Buy-and-hold"
              value={fmtPct(data.buy_hold_return)}
              color={data.buy_hold_return >= 0 ? "text-dark-text" : "text-red-500"}
            />
            <MetricCard
              label="Sharpe ratio"
              value={data.sharpe?.toFixed(2) ?? "—"}
              color={data.sharpe != null && data.sharpe > 1 ? "text-green-600" : "text-dark-text"}
            />
            <MetricCard
              label="Max drawdown"
              value={fmtPct(data.max_drawdown)}
              color="text-red-500"
            />
            <MetricCard
              label="Win rate"
              value={data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—"}
            />
            <MetricCard label="# Trades" value={String(data.num_trades)} />
            <MetricCard
              label="Avg win"
              value={data.avg_win != null ? fmtPct(data.avg_win) : "—"}
              color="text-green-600"
            />
            <MetricCard
              label="Avg loss"
              value={data.avg_loss != null ? fmtPct(data.avg_loss) : "—"}
              color="text-red-500"
            />
          </div>

          {outperformance != null && (
            <div className={`rounded-lg px-4 py-3 text-sm ${outperformance >= 0 ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>
              Strategy {outperformance >= 0 ? "outperformed" : "underperformed"} buy-and-hold by{" "}
              <span className="font-semibold">{Math.abs(outperformance).toFixed(1)}pp</span> over the 5-year period.
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide mb-4">
              P&L curve vs buy-and-hold (5 years, cumulative %)
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  tickFormatter={(d: string) => d.slice(0, 7)}
                  interval={Math.floor(chartData.length / 6)}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
                  width={52}
                />
                <ReferenceLine y={0} stroke="#E2E8F0" />
                <Tooltip
                  formatter={(value) => {
                    const v = Number(value);
                    return [`${v > 0 ? "+" : ""}${v.toFixed(1)}%`];
                  }}
                  labelFormatter={(l) => `Date: ${l}`}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone" dataKey="strategy" name="Strategy"
                  stroke="#7C3AED" dot={false} strokeWidth={2}
                />
                <Line
                  type="monotone" dataKey="buyHold" name="Buy & Hold"
                  stroke="#94A3B8" dot={false} strokeWidth={1.5} strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {!data && !loading && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-light">
          Configure the strategy above and click Run to see results.
        </div>
      )}
    </div>
  );
}