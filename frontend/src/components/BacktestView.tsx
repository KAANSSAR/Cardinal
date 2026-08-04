import { useEffect, useState } from "react";
import { AreaChart, Area, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";
import { useTheme } from "../lib/ThemeContext";
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
    <div className="rounded-lg bg-term-panel-alt border border-term-border-faint p-3 text-center">
      <p className="text-[11px] font-mono text-term-text-faint mb-1 uppercase tracking-wide">{label}</p>
      <p className={`font-mono text-xl font-semibold ${color ?? "text-term-text"}`}>{value}</p>
    </div>
  );
}

/**
 * Reads a resolved CSS custom property value so Recharts (which needs
 * real color strings, not var() references) stays in sync as the
 * Amber/Cyan/Green terminal theme is switched.
 */
function useResolvedThemeColors() {
  const { theme } = useTheme();
  const [colors, setColors] = useState({
    accent: "#f5b942", textFaint: "#5c5854", border: "#2a2a2a", panel: "#111111",
  });

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setColors({
      accent: style.getPropertyValue("--color-term-accent").trim() || "#f5b942",
      textFaint: style.getPropertyValue("--color-term-text-faint").trim() || "#5c5854",
      border: style.getPropertyValue("--color-term-border").trim() || "#2a2a2a",
      panel: style.getPropertyValue("--color-term-panel").trim() || "#111111",
    });
  }, [theme]);

  return colors;
}

export default function BacktestView({ onRun, data, loading }: Props) {
  const [strategy, setStrategy] = useState<BacktestStrategy>("momentum");
  const [fastWindow, setFastWindow] = useState(50);
  const [slowWindow, setSlowWindow] = useState(200);
  const [lookback, setLookback] = useState(20);
  const [entryZ, setEntryZ] = useState(2.0);
  const themeColors = useResolvedThemeColors();

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
      <div className="rounded-lg border border-term-border bg-term-panel p-5">
        <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest mb-4">
          Strategy configuration
        </p>

        <div className="flex gap-2 mb-5">
          {(["momentum", "mean_reversion"] as BacktestStrategy[]).map((s) => (
            <button
              key={s}
              onClick={() => setStrategy(s)}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-mono font-medium transition-colors border ${
                strategy === s
                  ? "bg-term-accent/10 border-term-accent text-term-accent"
                  : "border-term-border text-term-text-dim hover:bg-term-panel-alt"
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
                <span className="text-sm font-medium text-term-text">Fast MA window</span>
                <span className="font-mono text-sm text-term-accent font-semibold">{fastWindow}d</span>
              </div>
              <input type="range" min={10} max={100} step={5} value={fastWindow}
                onChange={(e) => setFastWindow(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-term-panel-alt accent-term-accent cursor-pointer" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-term-text">Slow MA window</span>
                <span className="font-mono text-sm text-term-accent font-semibold">{slowWindow}d</span>
              </div>
              <input type="range" min={50} max={300} step={10} value={slowWindow}
                onChange={(e) => setSlowWindow(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-term-panel-alt accent-term-accent cursor-pointer" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-term-text">Lookback window</span>
                <span className="font-mono text-sm text-term-accent font-semibold">{lookback}d</span>
              </div>
              <input type="range" min={5} max={60} step={5} value={lookback}
                onChange={(e) => setLookback(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-term-panel-alt accent-term-accent cursor-pointer" />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-term-text">Entry threshold (σ)</span>
                <span className="font-mono text-sm text-term-accent font-semibold">{entryZ.toFixed(1)}σ</span>
              </div>
              <input type="range" min={1.0} max={3.0} step={0.25} value={entryZ}
                onChange={(e) => setEntryZ(+e.target.value)}
                className="w-full h-1.5 rounded-full bg-term-panel-alt accent-term-accent cursor-pointer" />
            </div>
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={loading}
          className="mt-5 w-full py-2.5 rounded-lg bg-term-accent text-term-bg font-mono font-bold uppercase tracking-wide text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
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
              color={data.total_return >= 0 ? "text-term-accent-2" : "text-term-danger"}
            />
            <MetricCard
              label="Buy-and-hold"
              value={fmtPct(data.buy_hold_return)}
              color={data.buy_hold_return >= 0 ? "text-term-text" : "text-term-danger"}
            />
            <MetricCard
              label="Sharpe ratio"
              value={data.sharpe?.toFixed(2) ?? "—"}
              color={data.sharpe != null && data.sharpe > 1 ? "text-term-accent-2" : "text-term-text"}
            />
            <MetricCard
              label="Max drawdown"
              value={fmtPct(data.max_drawdown)}
              color="text-term-danger"
            />
            <MetricCard
              label="Win rate"
              value={data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—"}
            />
            <MetricCard label="# Trades" value={String(data.num_trades)} />
            <MetricCard
              label="Avg win"
              value={data.avg_win != null ? fmtPct(data.avg_win) : "—"}
              color="text-term-accent-2"
            />
            <MetricCard
              label="Avg loss"
              value={data.avg_loss != null ? fmtPct(data.avg_loss) : "—"}
              color="text-term-danger"
            />
          </div>

          {outperformance != null && (
            <div className={`rounded-lg px-4 py-3 text-sm font-mono border ${
              outperformance >= 0
                ? "bg-term-accent-2/10 border-term-accent-2/30 text-term-accent-2"
                : "bg-term-danger/10 border-term-danger/30 text-term-danger"
            }`}>
              Strategy {outperformance >= 0 ? "outperformed" : "underperformed"} buy-and-hold by{" "}
              <span className="font-semibold">{Math.abs(outperformance).toFixed(1)}pp</span> over the 5-year period.
            </div>
          )}

          <div className="rounded-lg border border-term-border bg-term-panel p-5">
            <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest mb-4">
              P&L curve vs buy-and-hold (5 years, cumulative %)
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id="strategyFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={themeColors.accent} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={themeColors.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: themeColors.textFaint }}
                  tickFormatter={(d: string) => d.slice(0, 7)}
                  interval={Math.floor(chartData.length / 6)}
                  stroke={themeColors.border}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: themeColors.textFaint }}
                  tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
                  width={52}
                  stroke={themeColors.border}
                />
                <ReferenceLine y={0} stroke={themeColors.border} />
                <Tooltip
                  formatter={(value) => {
                    const v = Number(value);
                    return [`${v > 0 ? "+" : ""}${v.toFixed(1)}%`];
                  }}
                  labelFormatter={(l) => `Date: ${l}`}
                  contentStyle={{
                    fontSize: 12, borderRadius: 6,
                    background: themeColors.panel, border: `1px solid ${themeColors.border}`,
                    color: themeColors.textFaint,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: themeColors.textFaint }} />
                <Area
                  type="monotone" dataKey="strategy" name="Strategy"
                  stroke={themeColors.accent} strokeWidth={2.5}
                  fill="url(#strategyFill)" dot={false}
                />
                <Line
                  type="monotone" dataKey="buyHold" name="Buy & Hold"
                  stroke={themeColors.textFaint} dot={false} strokeWidth={1.5} strokeDasharray="4 3"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {!data && !loading && (
        <div className="rounded-lg border border-term-border bg-term-panel p-8 text-center text-sm font-mono text-term-text-faint">
          Configure the strategy above and click Run to see results.
        </div>
      )}
    </div>
  );
}