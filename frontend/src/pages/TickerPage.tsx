import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  fetchBacktest, fetchComps, fetchDCF, fetchQuant,
  type BacktestResponse, type BacktestStrategy,
  type CompsResponse, type DCFAssumptions, type DCFResponse, type QuantResponse,
} from "../lib/api";
import { useDebounce } from "../lib/useDebounce";
import TickerSearch from "../components/TickerSearch";
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

type SectionId = "sec-fundamental" | "sec-quant" | "sec-backtest";

const SECTIONS: { id: SectionId; label: string; colorClass: string }[] = [
  { id: "sec-fundamental", label: "Fundamental", colorClass: "text-term-accent border-term-accent" },
  { id: "sec-quant", label: "Quant", colorClass: "text-term-accent border-term-accent" },
  { id: "sec-backtest", label: "Backtest", colorClass: "text-term-accent border-term-accent" },
];

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();

  function goBack() {
    // Falls back to home if there's no history to return to — e.g. someone
    // lands directly on a shared /ticker/AAPL link with nothing to go back to.
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/");
    }
  }
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<SectionId>("sec-fundamental");

  // ── Fundamental ─────────────────────────────────────────────────────────
  const [assumptions, setAssumptions] = useState<DCFAssumptions>(DEFAULT_ASSUMPTIONS);
  const debouncedAssumptions = useDebounce(assumptions, 400);
  const [dcfData, setDcfData] = useState<DCFResponse | null>(null);
  const [dcfLoading, setDcfLoading] = useState(true);
  const [dcfError, setDcfError] = useState<string | null>(null);
  const [compsData, setCompsData] = useState<CompsResponse | null>(null);
  const [compsLoading, setCompsLoading] = useState(true);

  // ── Quant — fetched eagerly since it's always visible on the scroll page ──
  const [quantData, setQuantData] = useState<QuantResponse | null>(null);
  const [quantLoading, setQuantLoading] = useState(true);
  const [quantError, setQuantError] = useState<string | null>(null);

  // ── Backtest — stays on-demand via the Run button ─────────────────────────
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
    if (!symbol) return;
    setQuantLoading(true);
    setQuantError(null);
    fetchQuant(symbol)
      .then(setQuantData)
      .catch((err: unknown) => setQuantError(err instanceof ApiError ? err.message : "Failed to fetch quant data."))
      .finally(() => setQuantLoading(false));
  }, [symbol]);

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

  // ── Scroll-spy: highlight the nav pill for whichever section is in view ──
  const sectionRefs = useRef<Record<SectionId, HTMLElement | null>>({
    "sec-fundamental": null, "sec-quant": null, "sec-backtest": null,
  });

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) {
          const topMost = visible.reduce((a, b) => (a.boundingClientRect.top < b.boundingClientRect.top ? a : b));
          setActiveSection(topMost.target.id as SectionId);
        }
      },
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 }
    );
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) {
        sectionRefs.current[s.id] = el;
        observer.observe(el);
      }
    });

    // Edge case: the LAST section (Backtest) may be too short to ever push its
    // top edge into the observer's trigger band once the page hits its true
    // scroll limit — there's no more page below it to scroll further. Once
    // the user is scrolled to (near) the actual bottom, force the last
    // section active regardless of what the observer last reported.
    const lastSectionId = SECTIONS[SECTIONS.length - 1].id;
    function handleScroll() {
      const scrolledToBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8;
      if (scrolledToBottom) setActiveSection(lastSectionId);
    }
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll(); // covers landing already-scrolled (e.g. short viewport) on mount

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", handleScroll);
    };
  }, [symbol]);

  function scrollToSection(id: SectionId) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="flex items-start min-h-screen">
      {/* ── Main content panel ────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 transition-all duration-300">

        {/* Sticky company header + nav — pinned just below the global Header,
            offset dynamically via --cardinal-header-height (see Header.tsx) */}
        <div className="sticky z-30" style={{ top: "var(--cardinal-header-height)" }}>

          {/* Header row */}
          <div className="border-b border-term-border-faint bg-term-bg">
            <div className="max-w-6xl mx-auto px-6 py-5 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <button
                  onClick={goBack}
                  aria-label="Go back"
                  title="Back"
                  className="shrink-0 mt-1 w-8 h-8 rounded-lg border border-term-border flex items-center justify-center text-term-text-dim hover:text-term-text hover:bg-term-panel-alt transition-colors"
                >
                  ‹
                </button>
                <div>
                  <h1 className="font-display text-3xl font-semibold text-term-text">
                    {dcfData?.company_name ?? symbol}
                  </h1>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="font-mono text-sm text-term-text-dim">{symbol?.toUpperCase()}</p>
                    {dcfData?.exchange && (
                      <span className="text-[11px] font-mono text-term-text-faint border border-term-border rounded px-1.5 py-0.5">
                        {dcfData.exchange}
                      </span>
                    )}
                    {dcfData?.currency && dcfData.currency !== "USD" && (
                      <span className="text-[11px] font-mono font-medium text-term-accent bg-term-accent/10 border border-term-accent/30 rounded px-1.5 py-0.5">
                        {dcfData.currency}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              {dcfData && (
                <div className="text-right shrink-0">
                  <p className="font-mono text-2xl font-semibold text-term-text tabular-nums">
                    {dcfData.current_price.toFixed(2)} <span className="text-sm text-term-text-faint">{dcfData.currency}</span>
                  </p>
                  {dcfData.current_price_usd != null && dcfData.currency !== "USD" && (
                    <p className="font-mono text-sm text-term-text-dim">${dcfData.current_price_usd.toFixed(2)} USD</p>
                  )}
                  {!dcfData.is_partial && dcfData.premium_discount_pct != null && (
                    <p className={`font-mono text-sm font-medium ${dcfData.premium_discount_pct > 0 ? "text-term-danger" : "text-term-accent-2"}`}>
                      {dcfData.premium_discount_pct > 0 ? "+" : ""}
                      {(dcfData.premium_discount_pct * 100).toFixed(1)}% vs intrinsic
                    </p>
                  )}
                  {dcfData.is_partial && (
                    <p className="font-mono text-sm text-term-accent">DCF data unavailable</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Nav row — compact search + anchor pills + AI TEAM toggle */}
          <div className="border-b border-term-border-faint bg-term-bg-alt">
            <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4 flex-wrap">
              <div className="flex-1 max-w-md">
                <TickerSearch hideButton />
              </div>
              <div className="flex items-center gap-1">
                {SECTIONS.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => scrollToSection(s.id)}
                    className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wide border transition-colors ${
                      activeSection === s.id
                        ? "border-term-accent text-term-accent bg-term-accent/10"
                        : "border-transparent text-term-text-faint hover:text-term-text-dim"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setSidebarOpen((o) => !o)}
                className={`ml-auto px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wide border transition-colors ${
                  sidebarOpen
                    ? "border-term-border-light text-term-text bg-term-panel-alt"
                    : "border-term-border text-term-text-dim hover:text-term-text"
                }`}
              >
                AI Team ▸
              </button>
            </div>
          </div>
        </div>

        {/* Sections — continuous scroll, all visible */}
        <div className="max-w-6xl mx-auto px-6 py-10 space-y-16">

          {/* ── Fundamental ──────────────────────────────────────────────── */}
          <section id="sec-fundamental" className="scroll-mt-6">
            <p className="font-mono text-[11px] text-term-accent uppercase tracking-widest mb-4">
              Fundamental — DCF Valuation
            </p>
            <div className="space-y-6">
              {dcfError && (
                <div className="rounded-lg border border-term-danger/40 bg-term-danger/10 px-4 py-3 text-sm text-term-danger">
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
                  <div className="rounded-lg border border-term-border bg-term-panel p-5 flex items-center justify-center min-h-[200px]">
                    <p className="text-term-text-dim text-sm font-mono animate-pulse">Running DCF valuation…</p>
                  </div>
                ) : dcfData ? (
                  <DCFOutputCard data={dcfData} />
                ) : null}
              </div>
              {compsLoading ? (
                <div className="rounded-lg border border-term-border bg-term-panel p-5">
                  <p className="text-term-text-dim text-sm font-mono animate-pulse">Loading comparable companies…</p>
                </div>
              ) : compsData ? (
                <CompsTable data={compsData} />
              ) : null}
            </div>
          </section>

          {/* ── Quant ────────────────────────────────────────────────────── */}
          <section id="sec-quant" className="scroll-mt-6">
            <p className="font-mono text-[11px] text-term-accent uppercase tracking-widest mb-4">
              Quant — Signal Analysis
            </p>
            {quantError && (
              <div className="rounded-lg border border-term-danger/40 bg-term-danger/10 px-4 py-3 text-sm text-term-danger mb-6">
                {quantError}
              </div>
            )}
            {quantLoading && (
              <div className="rounded-lg border border-term-border bg-term-panel p-8 text-center">
                <p className="text-term-text-dim text-sm font-mono animate-pulse">Computing quant signals…</p>
              </div>
            )}
            {quantData && !quantLoading && <QuantDashboard data={quantData} />}
          </section>

          {/* ── Backtest ─────────────────────────────────────────────────── */}
          <section id="sec-backtest" className="scroll-mt-6">
            <p className="font-mono text-[11px] text-term-accent uppercase tracking-widest mb-4">
              Backtest — Algo Strategy
            </p>
            <BacktestView
              onRun={handleRunBacktest}
              data={backtestData}
              loading={backtestLoading}
            />
          </section>
        </div>
      </div>

      {/* ── AI Sidebar panel — part of the page flow, not floating ───────── */}
      <div
        className={`shrink-0 sticky top-0 h-screen border-l border-term-border bg-term-panel overflow-hidden transition-all duration-300 ease-in-out ${
          sidebarOpen ? "w-[420px]" : "w-0"
        }`}
      >
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