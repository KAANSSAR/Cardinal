import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, fetchComps, fetchDCF, type CompsResponse, type DCFAssumptions, type DCFResponse } from "../lib/api";
import { useDebounce } from "../lib/useDebounce";
import AssumptionsPanel from "../components/AssumptionsPanel";
import DCFOutputCard from "../components/DCFOutputCard";
import CompsTable from "../components/CompsTable";

const DEFAULT_ASSUMPTIONS: DCFAssumptions = {
  growth_rate: 0.08,
  terminal_growth_rate: 0.035,
  projection_years: 5,
  wacc_override: undefined,
};

type Tab = "fundamental" | "quant" | "backtest";

const TABS: { key: Tab; label: string; colorClass: string; available: boolean }[] = [
  { key: "fundamental", label: "Fundamental", colorClass: "border-teal text-teal", available: true },
  { key: "quant", label: "Quant", colorClass: "border-blue text-blue", available: false },
  { key: "backtest", label: "Backtest", colorClass: "border-purple text-purple", available: false },
];

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [tab, setTab] = useState<Tab>("fundamental");
  const [assumptions, setAssumptions] = useState<DCFAssumptions>(DEFAULT_ASSUMPTIONS);
  const debouncedAssumptions = useDebounce(assumptions, 400);

  const [dcfData, setDcfData] = useState<DCFResponse | null>(null);
  const [dcfLoading, setDcfLoading] = useState(true);
  const [dcfError, setDcfError] = useState<string | null>(null);

  const [compsData, setCompsData] = useState<CompsResponse | null>(null);
  const [compsLoading, setCompsLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setDcfLoading(true);
    setDcfError(null);
    const params = { ...debouncedAssumptions };
    if (params.wacc_override === undefined) delete params.wacc_override;
    fetchDCF(symbol, params)
      .then(setDcfData)
      .catch((err: unknown) => setDcfError(err instanceof ApiError ? err.message : "Failed to fetch DCF data."))
      .finally(() => setDcfLoading(false));
  }, [symbol, debouncedAssumptions]);

  useEffect(() => {
    if (!symbol) return;
    setCompsLoading(true);
    fetchComps(symbol)
      .then(setCompsData)
      .catch(() => setCompsData(null))
      .finally(() => setCompsLoading(false));
  }, [symbol]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-dark-text">
            {dcfData?.company_name ?? symbol}
          </h1>
          <p className="font-mono text-sm text-slate">{symbol?.toUpperCase()}</p>
        </div>
        {dcfData && (
          <div className="text-right shrink-0">
            <p className="font-mono text-2xl font-semibold text-dark-text">${dcfData.current_price.toFixed(2)}</p>
            <p className={`text-sm font-medium ${dcfData.premium_discount_pct > 0 ? "text-red-500" : "text-green-600"}`}>
              {dcfData.premium_discount_pct > 0 ? "+" : ""}
              {(dcfData.premium_discount_pct * 100).toFixed(1)}% vs intrinsic
            </p>
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-8">
        {TABS.map((t) => (
          <button
            key={t.key}
            disabled={!t.available}
            onClick={() => t.available && setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              t.available && tab === t.key ? t.colorClass
              : t.available ? "border-transparent text-slate hover:text-slate-dark"
              : "border-transparent text-slate-light cursor-not-allowed"
            }`}
          >
            {t.label}
            {!t.available && <span className="ml-1.5 text-[10px] align-top opacity-60">soon</span>}
          </button>
        ))}
      </div>

      {tab === "fundamental" && (
        <div className="space-y-6">
          {dcfError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{dcfError}</div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.6fr] gap-6">
            <AssumptionsPanel
              assumptions={assumptions}
              onChange={(next) => setAssumptions((prev) => ({ ...prev, ...next }))}
              loading={dcfLoading}
            />
            {dcfLoading && !dcfData ? (
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm flex items-center justify-center min-h-[200px]">
                <p className="text-slate text-sm animate-pulse">Running DCF valuation…</p>
              </div>
            ) : dcfData ? (
              <DCFOutputCard data={dcfData} />
            ) : null}
          </div>

          {compsLoading ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-slate text-sm animate-pulse">Loading comparable companies…</p>
            </div>
          ) : compsData ? (
            <CompsTable data={compsData} />
          ) : null}
        </div>
      )}
    </div>
  );
}