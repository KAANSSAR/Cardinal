import type { DCFAssumptions } from "../lib/api";

interface Props {
  assumptions: DCFAssumptions;
  onChange: (next: Partial<DCFAssumptions>) => void;
  loading: boolean;
}

function SliderRow({ label, sublabel, min, max, step, value, display, onChange }: {
  label: string; sublabel?: string; min: number; max: number;
  step: number; value: number; display: string; onChange: (v: number) => void;
}) {
  return (
    <div className="py-3">
      <div className="flex justify-between items-baseline mb-1.5">
        <div>
          <span className="text-sm font-medium text-dark-text">{label}</span>
          {sublabel && <span className="ml-1.5 text-xs text-slate-light">{sublabel}</span>}
        </div>
        <span className="font-mono text-sm font-semibold text-teal">{display}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-full bg-slate-200 accent-teal cursor-pointer"
      />
    </div>
  );
}

export default function AssumptionsPanel({ assumptions, onChange, loading }: Props) {
  const fmt = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="font-mono text-[11px] text-slate-light uppercase tracking-wide">Model assumptions</p>
        {loading && <span className="text-xs text-teal animate-pulse">Recalculating…</span>}
      </div>

      <div className="divide-y divide-slate-100">
        <SliderRow
          label="FCF Growth Rate" sublabel="projection period"
          min={-0.1} max={0.3} step={0.005} value={assumptions.growth_rate}
          display={fmt(assumptions.growth_rate)}
          onChange={(v) => onChange({ growth_rate: v })}
        />
        <SliderRow
          label="Terminal Growth Rate"
          min={0.005} max={0.07} step={0.005} value={assumptions.terminal_growth_rate}
          display={fmt(assumptions.terminal_growth_rate)}
          onChange={(v) => onChange({ terminal_growth_rate: v })}
        />
        <SliderRow
          label="WACC Override" sublabel="leave at 9% to use CAPM"
          min={0.04} max={0.20} step={0.005} value={assumptions.wacc_override ?? 0.09}
          display={assumptions.wacc_override != null ? fmt(assumptions.wacc_override) : "auto"}
          onChange={(v) => onChange({ wacc_override: v })}
        />
        <SliderRow
          label="Projection Years"
          min={3} max={10} step={1} value={assumptions.projection_years}
          display={`${assumptions.projection_years}y`}
          onChange={(v) => onChange({ projection_years: Math.round(v) })}
        />
      </div>

      <button
        className="mt-3 text-xs text-slate hover:text-teal transition-colors"
        onClick={() => onChange({ growth_rate: 0.08, terminal_growth_rate: 0.035, projection_years: 5, wacc_override: undefined })}
      >
        Reset to defaults
      </button>
    </div>
  );
}