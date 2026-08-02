import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  ApiError,
  fetchBacktest, fetchComps, fetchDCF, fetchQuant,
  type BacktestResponse, type BacktestStrategy,
  type CompsResponse, type DCFAssumptions, type DCFResponse, type QuantResponse,
} from "../lib/api";
import { useDebounce } from "../lib/useDebounce";
import AssumptionsPanel from "../components/AssumptionsPanel";
import DCFOutputCard from "../components/DCFOutputCard";
import CompsTable from "../components/CompsTable";
import QuantDashboard from "../components/QuantDashboard";
import BacktestView from "../components/BacktestView";
import AISidebar from "../components/AISidebar";

const DEFAULT_ASSUMPTIONS: DCFAssumptions = {
  growth_rate: 0.08,
  terminal_growth_rate: 0.035,
  projection_years: 5,
  wacc_override: undefined,
};

type Tab = "fundamental" | "quant" | "backtest";

const TABS: { key: Tab; label: string; colorClass: string }[] = [
  { key: "fundamental", label: "Fundamental", colorClass: "border-teal text-teal" },
  { key: "quant", label: "Quant", colorClass: "border-blue text-blue" },
  { key: "backtest", label: "Backtest", colorClass: "border-purple text-purple" },
];

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [tab, setTab] = useState<Tab>("fundamental");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── Fundamental ─────────────────────────────────────────────────────────
  const [assumptions, setAssumptions] = useState<DCFAssumptions>(DEFAULT_ASSUMPTIONS);
  const debouncedAssumptions = useDebounce(assumptions, 400);
  const [dcfData, setDcfData] = useState<DCFResponse | null>(null);
  const [dcfLoading, setDcfLoading] = useState(true);
  const [dcfError, setDcfError] = useState<string | null>(null);
  const [compsData, setCompsData] = useState<CompsResponse | null>(null);
  const [compsLoading, setCompsLoading] = useState(true);

  // ── Quant ────────────────────────────────────────────────────────────────
  const [quantData, setQuantData] = useState<QuantResponse | null>(null);
  const [quantLoading, setQuantLoading] = useState(false);
  const [quantError, setQuantError] = useState<string | null>(null);

  // ── Backtest ─────────────────────────────────────────────────────────────
  const [backtestData, setBacktestData] = useState<BacktestResponse | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestStrategy, setBacktestStrategy] = useState<BacktestStrategy>("momentum");

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

  useEffect(() => {
    if (tab !== "quant" || !symbol || quantData || quantLoading) return;
    setQuantLoading(true);
    setQuantError(null);
    fetchQuant(symbol)
      .then(setQuantData)
      .catch((err: unknown) => setQuantError(err instanceof ApiError ? err.message : "Failed to fetch quant data."))
      .finally(() => setQuantLoading(false));
  }, [tab, symbol]);

  function handleRunBacktest(strategy: BacktestStrategy, params: Record<string, number>) {
    if (!symbol) return;
    setBacktestStrategy(strategy);
    setBacktestLoading(true);
    fetchBacktest(symbol, strategy, params)
      .then(setBacktestData)
      .catch(() => setBacktestData(null))
      .finally(() => setBacktestLoading(false));
  }

  useEffect(() => {
    setQuantData(null);
    setBacktestData(null);
    setQuantError(null);
  }, [symbol]);

  return (
    // Flex row — content shifts left when sidebar opens
    <div className="flex items-start min-h-screen">

      {/* ── Main content panel ────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 px-6 py-10 transition-all duration-300">
        <div className="max-w-5xl mx-auto">

          {/* Header */}
          <div className="flex items-start justify-between mb-6 gap-4">
            <div>
              <h1 className="font-display text-3xl font-semibold text-dark-text">
                {dcfData?.company_name ?? symbol}
              </h1>
              <p className="font-mono text-sm text-slate">{symbol?.toUpperCase()}</p>
            </div>
            {dcfData && (
              <div className="text-right shrink-0">
                <p className="font-mono text-2xl font-semibold text-dark-text">
                  ${dcfData.current_price.toFixed(2)}
                </p>
                <p className={`text-sm font-medium ${dcfData.premium_discount_pct > 0 ? "text-red-500" : "text-green-600"}`}>
                  {dcfData.premium_discount_pct > 0 ? "+" : ""}
                  {(dcfData.premium_discount_pct * 100).toFixed(1)}% vs intrinsic
                </p>
              </div>
            )}
          </div>

          {/* Tab bar — AI sits right after Backtest */}
          <div className="flex items-end gap-1 border-b border-slate-200 mb-8">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  tab === t.key ? t.colorClass : "border-transparent text-slate hover:text-slate-dark"
                }`}
              >
                {t.label}
              </button>
            ))}
            {/* AI tab — no border, sits right after Backtest */}
            <button
              onClick={() => setSidebarOpen((o) => !o)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                sidebarOpen
                  ? "border-slate-400 text-slate-dark"
                  : "border-transparent text-slate-light hover:text-slate"
              }`}
            >
              AI
            </button>
          </div>

          {/* Tab content */}
          {tab === "fundamental" && (
            <div className="space-y-6">
              {dcfError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {dcfError}
                </div>
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

          {tab === "quant" && (
            <div>
              {quantError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-6">
                  {quantError}
                </div>
              )}
              {quantLoading && (
                <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
                  <p className="text-slate text-sm animate-pulse">Computing quant signals…</p>
                </div>
              )}
              {quantData && !quantLoading && <QuantDashboard data={quantData} />}
            </div>
          )}

          {tab === "backtest" && (
            <BacktestView
              onRun={handleRunBacktest}
              data={backtestData}
              loading={backtestLoading}
            />
          )}
        </div>
      </div>

      {/* ── AI Sidebar panel — part of the page flow, not floating ───────── */}
      <div
        className={`shrink-0 sticky top-0 h-screen border-l border-slate-200 bg-white overflow-hidden transition-all duration-300 ease-in-out ${
          sidebarOpen ? "w-[420px]" : "w-0"
        }`}
      >
        {/* Only render content when open so offscreen agents don't flash */}
        {sidebarOpen && (
          <AISidebar
            ticker={symbol ?? ""}
            assumptions={assumptions}
            strategy={backtestStrategy}
            onClose={() => setSidebarOpen(false)}
          />
        )}
      </div>
    </div>
  );
}