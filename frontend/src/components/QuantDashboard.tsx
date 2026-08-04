import type { QuantResponse } from "../lib/api";

interface Props {
  data: QuantResponse;
}

function fmtPct(v: number | null): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: number | null, dp = 2): string {
  return v == null ? "—" : v.toFixed(dp);
}

type Signal = "BULLISH" | "BEARISH" | "NEUTRAL" | "STRONG" | "WEAK" | "OVERSOLD" | "OVERBOUGHT" | "HIGH BETA" | "LOW";

// Semantic mapping per design tokens: accent2=positive, danger=negative,
// accent=primary/warn (used for "notable but not necessarily bad" signals like high beta).
function getSignal(metric: string, value: number | null): { signal: Signal; color: string } {
  if (value == null) return { signal: "NEUTRAL", color: "text-term-text-dim" };

  switch (metric) {
    case "momentum":
      if (value > 0.3) return { signal: "BULLISH", color: "text-term-accent-2" };
      if (value < -0.3) return { signal: "BEARISH", color: "text-term-danger" };
      return { signal: "NEUTRAL", color: "text-term-text-dim" };
    case "sharpe":
      if (value > 1.0) return { signal: "STRONG", color: "text-term-accent-2" };
      if (value < 0) return { signal: "WEAK", color: "text-term-danger" };
      return { signal: "NEUTRAL", color: "text-term-text-dim" };
    case "rsi":
      if (value < 30) return { signal: "OVERSOLD", color: "text-term-accent-2" };
      if (value > 70) return { signal: "OVERBOUGHT", color: "text-term-danger" };
      return { signal: "NEUTRAL", color: "text-term-text-dim" };
    case "beta":
      if (value > 1.5) return { signal: "HIGH BETA", color: "text-term-accent" };
      if (value < 0.5) return { signal: "LOW", color: "text-term-text-dim" };
      return { signal: "NEUTRAL", color: "text-term-text-dim" };
    default:
      return { signal: "NEUTRAL", color: "text-term-text-dim" };
  }
}

function SignalBadge({ signal, color }: { signal: Signal; color: string }) {
  const bgClass = color.replace("text-", "bg-") + "/10";
  const borderClass = color.replace("text-", "border-") + "/30";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold ${color} ${bgClass} border ${borderClass}`}>
      {signal}
    </span>
  );
}

function Row({ label, value, signal, signalColor, interpretation }: {
  label: string;
  value: string;
  signal: Signal;
  signalColor: string;
  interpretation: string;
}) {
  return (
    <tr className="border-b border-term-border-faint hover:bg-term-panel-alt transition-colors">
      <td className="py-2.5 pr-3 text-sm text-term-text-dim">{label}</td>
      <td className="py-2.5 px-3 font-mono text-sm font-semibold text-term-text">{value}</td>
      <td className="py-2.5 px-3 text-xs text-term-text-faint hidden sm:table-cell">{interpretation}</td>
      <td className="py-2.5 pl-3 text-right">
        <SignalBadge signal={signal} color={signalColor} />
      </td>
    </tr>
  );
}

export default function QuantDashboard({ data }: Props) {
  const vols = [
    { label: "10d", value: data.vol_10d },
    { label: "30d", value: data.vol_30d },
    { label: "60d", value: data.vol_60d },
    { label: "252d", value: data.vol_252d },
  ];
  const annualVol = data.vol_252d ?? 0;

  return (
    <div className="space-y-6">
      {/* Signal table */}
      <div className="rounded-lg border border-term-border bg-term-panel p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest">
            Signal dashboard
          </p>
          <span className="text-[11px] font-mono text-term-text-faint">
            Benchmark: <span className="text-term-text-dim">{data.benchmark}</span>
          </span>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-term-border-faint text-[11px] font-mono uppercase tracking-wide text-term-text-faint">
              <th className="text-left py-2 pr-3 font-medium">Metric</th>
              <th className="text-left py-2 px-3 font-medium">Value</th>
              <th className="text-left py-2 px-3 font-medium hidden sm:table-cell">Interpretation</th>
              <th className="text-right py-2 pl-3 font-medium">Signal</th>
            </tr>
          </thead>
          <tbody>
            {(["momentum_20d", "momentum_60d", "momentum_252d"] as const).map((key) => {
              const window = key.replace("momentum_", "");
              const val = data[key];
              const { signal, color } = getSignal("momentum", val);
              const interp = val == null ? "Insufficient data"
                : val > 0.3 ? "Strong upward trend"
                : val < -0.3 ? "Strong downward trend"
                : "Trend is neutral";
              return (
                <Row key={key} label={`Momentum (${window})`} value={fmtNum(val, 4)}
                  signal={signal} signalColor={color} interpretation={interp} />
              );
            })}

            {(["sharpe_60d", "sharpe_252d"] as const).map((key) => {
              const window = key.replace("sharpe_", "");
              const val = data[key];
              const { signal, color } = getSignal("sharpe", val);
              return (
                <Row key={key} label={`Rolling Sharpe (${window})`} value={fmtNum(val, 4)}
                  signal={signal} signalColor={color}
                  interpretation={val == null ? "—" : val > 1 ? "Risk well compensated" : val < 0 ? "Return < risk-free rate" : "Moderate risk-adj return"} />
              );
            })}

            <Row
              label="Beta vs benchmark" value={fmtNum(data.beta, 3)}
              signal={getSignal("beta", data.beta).signal}
              signalColor={getSignal("beta", data.beta).color}
              interpretation={data.beta == null ? "—" : `Moves ${data.beta.toFixed(2)}× the benchmark`}
            />

            <Row
              label="RSI (14-period)" value={fmtNum(data.rsi, 1)}
              signal={getSignal("rsi", data.rsi).signal}
              signalColor={getSignal("rsi", data.rsi).color}
              interpretation={
                data.rsi == null ? "—"
                : data.rsi < 30 ? "Approaching oversold territory"
                : data.rsi > 70 ? "Approaching overbought territory"
                : "Within normal range"
              }
            />

            <Row
              label="Bollinger %B" value={fmtNum(data.bb_pct_b, 3)}
              signal={
                data.bb_pct_b == null ? "NEUTRAL"
                : data.bb_pct_b < 0.2 ? "OVERSOLD"
                : data.bb_pct_b > 0.8 ? "OVERBOUGHT"
                : "NEUTRAL"
              }
              signalColor={
                data.bb_pct_b == null ? "text-term-text-dim"
                : data.bb_pct_b < 0.2 ? "text-term-accent-2"
                : data.bb_pct_b > 0.8 ? "text-term-danger"
                : "text-term-text-dim"
              }
              interpretation={
                data.bb_pct_b == null ? "—"
                : data.bb_pct_b < 0 ? "Price below lower band"
                : data.bb_pct_b > 1 ? "Price above upper band"
                : `${((data.bb_pct_b) * 100).toFixed(0)}% of band width from lower`
              }
            />
          </tbody>
        </table>
      </div>

      {/* Volatility surface */}
      <div className="rounded-lg border border-term-border bg-term-panel p-5">
        <p className="font-mono text-[11px] text-term-text-faint uppercase tracking-widest mb-4">
          Volatility surface — realised annualised vol
        </p>
        <div className="flex gap-3">
          {vols.map(({ label, value }) => {
            const isElevated = value != null && annualVol > 0 && value > annualVol * 1.15;
            return (
              <div key={label} className={`flex-1 rounded-lg p-3 text-center border ${isElevated ? "border-term-accent/40 bg-term-accent/5" : "border-term-border-faint bg-term-panel-alt"}`}>
                <p className="text-[11px] font-mono text-term-text-faint mb-1">{label}</p>
                <p className={`font-mono text-lg font-semibold ${isElevated ? "text-term-accent" : "text-term-text"}`}>
                  {fmtPct(value)}
                </p>
                {isElevated && <p className="text-[10px] font-mono text-term-accent mt-0.5 uppercase">elevated</p>}
              </div>
            );
          })}
        </div>

        {data.bb_upper != null && (
          <div className="mt-4 pt-4 border-t border-term-border-faint grid grid-cols-3 gap-3">
            {[
              { label: "Upper band (2σ)", val: data.bb_upper },
              { label: "Middle (20d SMA)", val: data.bb_middle },
              { label: "Lower band (2σ)", val: data.bb_lower },
            ].map(({ label, val }) => (
              <div key={label}>
                <p className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">{label}</p>
                <p className="font-mono text-sm font-medium text-term-text">${val?.toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}