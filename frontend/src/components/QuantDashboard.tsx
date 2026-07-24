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

type Signal = "BULLISH" | "BEARISH" | "NEUTRAL" | "STRONG" | "WEAK" | "OVERSOLD" | "OVERBOUGHT" | "ELEVATED" | "HIGH BETA" | "LOW";

function getSignal(metric: string, value: number | null): { signal: Signal; color: string } {
  if (value == null) return { signal: "NEUTRAL", color: "text-slate" };

  switch (metric) {
    case "momentum":
      if (value > 0.3) return { signal: "BULLISH", color: "text-green-600" };
      if (value < -0.3) return { signal: "BEARISH", color: "text-red-500" };
      return { signal: "NEUTRAL", color: "text-amber-500" };
    case "sharpe":
      if (value > 1.0) return { signal: "STRONG", color: "text-green-600" };
      if (value < 0) return { signal: "WEAK", color: "text-red-500" };
      return { signal: "NEUTRAL", color: "text-amber-500" };
    case "rsi":
      if (value < 30) return { signal: "OVERSOLD", color: "text-green-600" };
      if (value > 70) return { signal: "OVERBOUGHT", color: "text-red-500" };
      return { signal: "NEUTRAL", color: "text-slate-dark" };
    case "beta":
      if (value > 1.5) return { signal: "HIGH BETA", color: "text-amber-500" };
      if (value < 0.5) return { signal: "LOW", color: "text-blue-500" };
      return { signal: "NEUTRAL", color: "text-slate-dark" };
    default:
      return { signal: "NEUTRAL", color: "text-slate-dark" };
  }
}

function SignalBadge({ signal, color }: { signal: Signal; color: string }) {
  const bg = color.replace("text-", "bg-").replace("-600", "-50").replace("-500", "-50");
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${color} ${bg} border border-current border-opacity-20`}>
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
    <tr className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
      <td className="py-2.5 pr-3 text-sm text-slate-dark">{label}</td>
      <td className="py-2.5 px-3 font-mono text-sm font-semibold text-dark-text">{value}</td>
      <td className="py-2.5 px-3 text-xs text-slate hidden sm:table-cell">{interpretation}</td>
      <td className="py-2.5 pl-3 text-right">
        <SignalBadge signal={signal} color={signalColor} />
      </td>
    </tr>
  );
}

export default function QuantDashboard({ data }: Props) {
  // Volatility term structure
  const vols = [
    { label: "10d", value: data.vol_10d },
    { label: "30d", value: data.vol_30d },
    { label: "60d", value: data.vol_60d },
    { label: "252d", value: data.vol_252d },
  ];

  return (
    <div className="space-y-6">
      {/* Signal table */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide">
            Signal dashboard
          </p>
          <span className="text-[11px] text-slate-light">
            Benchmark: <span className="font-mono text-slate-dark">{data.benchmark}</span>
          </span>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-dark">
              <th className="text-left py-2 pr-3 font-medium">Metric</th>
              <th className="text-left py-2 px-3 font-medium">Value</th>
              <th className="text-left py-2 px-3 font-medium hidden sm:table-cell">Interpretation</th>
              <th className="text-right py-2 pl-3 font-medium">Signal</th>
            </tr>
          </thead>
          <tbody>
            {/* Momentum */}
            {(["momentum_20d", "momentum_60d", "momentum_252d"] as const).map((key) => {
              const window = key.replace("momentum_", "").replace("d", "d");
              const val = data[key];
              const { signal, color } = getSignal("momentum", val);
              const interp = val == null ? "Insufficient data"
                : val > 0.3 ? "Strong upward trend"
                : val < -0.3 ? "Strong downward trend"
                : "Trend is neutral";
              return (
                <Row
                  key={key}
                  label={`Momentum (${window})`}
                  value={fmtNum(val, 4)}
                  signal={signal}
                  signalColor={color}
                  interpretation={interp}
                />
              );
            })}

            {/* Sharpe */}
            {(["sharpe_60d", "sharpe_252d"] as const).map((key) => {
              const window = key.replace("sharpe_", "").replace("d", "d");
              const val = data[key];
              const { signal, color } = getSignal("sharpe", val);
              return (
                <Row
                  key={key}
                  label={`Rolling Sharpe (${window})`}
                  value={fmtNum(val, 4)}
                  signal={signal}
                  signalColor={color}
                  interpretation={val == null ? "—" : val > 1 ? "Risk well compensated" : val < 0 ? "Return < risk-free rate" : "Moderate risk-adj return"}
                />
              );
            })}

            {/* Beta */}
            <Row
              label="Beta vs benchmark"
              value={fmtNum(data.beta, 3)}
              signal={getSignal("beta", data.beta).signal}
              signalColor={getSignal("beta", data.beta).color}
              interpretation={data.beta == null ? "—" : `Moves ${data.beta.toFixed(2)}× the benchmark`}
            />

            {/* RSI */}
            <Row
              label="RSI (14-period)"
              value={fmtNum(data.rsi, 1)}
              signal={getSignal("rsi", data.rsi).signal}
              signalColor={getSignal("rsi", data.rsi).color}
              interpretation={
                data.rsi == null ? "—"
                : data.rsi < 30 ? "Approaching oversold territory"
                : data.rsi > 70 ? "Approaching overbought territory"
                : "Within normal range"
              }
            />

            {/* Bollinger %B */}
            <Row
              label="Bollinger %B"
              value={fmtNum(data.bb_pct_b, 3)}
              signal={
                data.bb_pct_b == null ? "NEUTRAL"
                : data.bb_pct_b < 0.2 ? "OVERSOLD"
                : data.bb_pct_b > 0.8 ? "OVERBOUGHT"
                : "NEUTRAL"
              }
              signalColor={
                data.bb_pct_b == null ? "text-slate"
                : data.bb_pct_b < 0.2 ? "text-green-600"
                : data.bb_pct_b > 0.8 ? "text-red-500"
                : "text-slate-dark"
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
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide mb-4">
          Volatility surface — realised annualised vol
        </p>
        <div className="flex gap-3">
          {vols.map(({ label, value }) => {
            const near = data.vol_10d ?? 0;
            const far = data.vol_252d ?? 0;
            const isElevated = value != null && far > 0 && value > far * 1.15;
            return (
              <div key={label} className={`flex-1 rounded-lg p-3 text-center border ${isElevated ? "border-amber/40 bg-amber/5" : "border-slate-100 bg-slate-50"}`}>
                <p className="text-[11px] text-slate-light mb-1">{label}</p>
                <p className={`font-mono text-lg font-semibold ${isElevated ? "text-amber-dark" : "text-dark-text"}`}>
                  {fmtPct(value)}
                </p>
                {isElevated && <p className="text-[10px] text-amber-dark mt-0.5">elevated</p>}
              </div>
            );
          })}
        </div>

        {/* Bollinger band levels */}
        {data.bb_upper != null && (
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-3 gap-3">
            {[
              { label: "Upper band (2σ)", val: data.bb_upper },
              { label: "Middle (20d SMA)", val: data.bb_middle },
              { label: "Lower band (2σ)", val: data.bb_lower },
            ].map(({ label, val }) => (
              <div key={label}>
                <p className="text-[11px] text-slate-light">{label}</p>
                <p className="font-mono text-sm font-medium text-dark-text">${val?.toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}