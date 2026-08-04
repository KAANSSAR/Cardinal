import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useTheme } from "../lib/ThemeContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Metrics {
  total_calls: number;
  gt_entries: number;
  verified: number;
  total_feedback: number;
  positive: number;
  approval_rate: number;
  gemini_calls: number;
  cache_hits: number;
  gt_hits: number;
  agent_stats: AgentStat[];
  recent_calls: RecentCall[];
  recent_feedback: RecentFeedback[];
  approval_threshold: number;
}

interface AgentStat {
  agent: string;
  total_calls: number;
  avg_ms: number;
  gemini_calls: number;
  cache_hits: number;
  gt_hits: number;
}

interface RecentCall {
  ticker: string;
  agent: string;
  response_time_ms: number;
  source: string;
  created_at: string;
}

interface RecentFeedback {
  ticker: string;
  agent: string;
  vote: string;
  comment: string | null;
  created_at: string;
}

interface GTEntry {
  id: number;
  ticker: string;
  agent: string;
  params_hash: string;
  verdict: string | null;
  approval_count: number;
  rejection_count: number;
  is_verified: number;
  response_time_ms: number | null;
  memo?: string;
  created_at: string;
  updated_at: string;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="bg-term-panel rounded-lg border border-term-border p-5">
      <p className="text-xs font-mono text-term-text-faint uppercase tracking-widest mb-2">{label}</p>
      <p className={`font-mono text-3xl font-bold ${accent ?? "text-term-text"}`}>{value}</p>
      {sub && <p className="text-xs font-mono text-term-text-faint mt-1">{sub}</p>}
    </div>
  );
}

// Agent identity colors — fixed, same reasoning as elsewhere: these code
// "which agent", not "which terminal theme is active".
const AGENT_COLOR: Record<string, string> = {
  xavi: "#5EEAD4",
  iniesta: "#818CF8",
  busquets: "#A78BFA",
  messi: "#F59E0B",
};

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    gemini: "bg-term-accent/10 text-term-accent border-term-accent/30",
    cache: "bg-term-text-dim/10 text-term-text-dim border-term-border-light",
    gt_db: "bg-term-accent-2/10 text-term-accent-2 border-term-accent-2/30",
  };
  return (
    <span className={`text-[10px] font-mono font-medium px-2 py-0.5 rounded-full border ${colors[source] ?? "bg-term-panel-alt text-term-text-faint border-term-border"}`}>
      {source}
    </span>
  );
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <span className="text-term-text-faint text-xs">—</span>;
  const colors: Record<string, string> = {
    BUY: "text-term-accent-2 bg-term-accent-2/10 border-term-accent-2/30",
    HOLD: "text-term-accent bg-term-accent/10 border-term-accent/30",
    SELL: "text-term-danger bg-term-danger/10 border-term-danger/30",
    BULLISH: "text-term-accent-2 bg-term-accent-2/10 border-term-accent-2/30",
    BEARISH: "text-term-danger bg-term-danger/10 border-term-danger/30",
    NEUTRAL: "text-term-text-dim bg-term-panel-alt border-term-border",
  };
  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${colors[verdict] ?? "bg-term-panel-alt text-term-text-dim border-term-border"}`}>
      {verdict}
    </span>
  );
}

/** Same reactive-theme-color pattern as BacktestView — Recharts needs real color strings. */
function useResolvedThemeColors() {
  const { theme } = useTheme();
  const [colors, setColors] = useState({ textFaint: "#5c5854", border: "#2a2a2a", panel: "#111111" });

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setColors({
      textFaint: style.getPropertyValue("--color-term-text-faint").trim() || "#5c5854",
      border: style.getPropertyValue("--color-term-border").trim() || "#2a2a2a",
      panel: style.getPropertyValue("--color-term-panel").trim() || "#111111",
    });
  }, [theme]);

  return colors;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [gtEntries, setGtEntries] = useState<GTEntry[]>([]);
  const [gtSearch, setGtSearch] = useState("");
  const [gtAgent, setGtAgent] = useState("");
  const [gtVerifiedOnly, setGtVerifiedOnly] = useState(false);
  const [expandedMemo, setExpandedMemo] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<"overview" | "groundtruth" | "activity" | "api">("overview");
  const themeColors = useResolvedThemeColors();

  const loadMetrics = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/metrics`);
      setMetrics(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadGT = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (gtAgent) params.set("agent", gtAgent);
      if (gtSearch) params.set("ticker", gtSearch.toUpperCase());
      if (gtVerifiedOnly) params.set("verified_only", "true");
      const res = await fetch(`${API_BASE}/admin/ground-truth?${params}`);
      setGtEntries(await res.json());
    } catch { /* ignore */ }
  }, [gtAgent, gtSearch, gtVerifiedOnly]);

  useEffect(() => {
    Promise.all([loadMetrics(), loadGT()]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadGT(); }, [gtAgent, gtSearch, gtVerifiedOnly]);

  async function deleteEntry(id: number) {
    if (!confirm("Delete this GT entry?")) return;
    await fetch(`${API_BASE}/admin/ground-truth/${id}`, { method: "DELETE" });
    setGtEntries((e) => e.filter((x) => x.id !== id));
  }

  const cacheHitRate = metrics
    ? Math.round(((metrics.cache_hits + metrics.gt_hits) / Math.max(metrics.total_calls, 1)) * 100)
    : 0;

  const NAV_ITEMS = [
    { key: "overview", label: "Overview" },
    { key: "groundtruth", label: "Ground Truth DB" },
    { key: "activity", label: "Activity" },
    { key: "api", label: "API Reference" },
  ] as const;

  const ENDPOINTS = [
    { method: "GET", path: "/health", desc: "Health check" },
    { method: "GET", path: "/search?q=...", desc: "Ticker + company name search" },
    { method: "GET", path: "/ticker/{symbol}/dcf", desc: "Full DCF valuation" },
    { method: "GET", path: "/ticker/{symbol}/comps", desc: "Comparable companies" },
    { method: "GET", path: "/ticker/{symbol}/quant", desc: "Quant signal snapshot" },
    { method: "GET", path: "/ticker/{symbol}/backtest", desc: "Algo backtest results" },
    { method: "GET", path: "/ticker/{symbol}/price-history", desc: "OHLCV price history" },
    { method: "GET", path: "/market/indices", desc: "Index quotes + sparklines" },
    { method: "GET", path: "/market/movers", desc: "Top gainers and losers" },
    { method: "GET", path: "/market/sectors", desc: "Sector heatmap" },
    { method: "GET", path: "/market/ticker-tape", desc: "Header marquee watchlist" },
    { method: "POST", path: "/agent/xavi", desc: "Fundamental Analyst memo" },
    { method: "POST", path: "/agent/iniesta", desc: "Quant signal memo" },
    { method: "POST", path: "/agent/busquets", desc: "Backtest strategy memo" },
    { method: "POST", path: "/agent/messi", desc: "Full orchestration + synthesis" },
    { method: "POST", path: "/agent/messi/chat", desc: "Messi follow-up chat" },
    { method: "POST", path: "/feedback", desc: "Submit agent feedback vote" },
    { method: "GET", path: "/admin/metrics", desc: "Platform metrics" },
    { method: "GET", path: "/admin/ground-truth", desc: "List GT DB entries" },
    { method: "DELETE", path: "/admin/ground-truth/{id}", desc: "Delete GT entry" },
  ];

  if (loading) return (
    <div className="flex items-center justify-center h-screen bg-term-bg" data-theme="amber">
      <div className="w-8 h-8 rounded-full border-2 border-term-accent border-t-transparent animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen bg-term-bg flex flex-col">
      {/* Top nav */}
      <header className="bg-term-bg-alt border-b border-term-border px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <p className="font-display text-lg font-semibold text-term-text">CARDINAL</p>
          <span className="text-term-text-faint text-sm font-mono uppercase tracking-wide">Admin</span>
        </div>
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              onClick={() => setActiveSection(item.key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-mono transition-colors ${
                activeSection === item.key ? "bg-term-panel-alt text-term-accent" : "text-term-text-faint hover:text-term-text-dim"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-mono text-term-text-faint hover:text-term-text-dim border border-term-border rounded-lg px-3 py-1.5 transition-colors"
        >
          FastAPI Docs ↗
        </a>
      </header>

      <main className="flex-1 px-8 py-8 max-w-7xl mx-auto w-full">

        {/* ── Overview ─────────────────────────────────────────────────────── */}
        {activeSection === "overview" && metrics && (
          <div className="space-y-8">
            <div>
              <h1 className="font-display text-2xl font-semibold text-term-text mb-1">Platform Overview</h1>
              <p className="text-sm text-term-text-dim">Real-time metrics across all Cardinal agents and endpoints.</p>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard label="Total agent calls" value={metrics.total_calls} sub="All agents + endpoints" />
              <KPICard label="Cache hit rate" value={`${cacheHitRate}%`} sub={`${metrics.cache_hits} mem · ${metrics.gt_hits} GT`} accent="text-term-accent" />
              <KPICard label="GT DB entries" value={metrics.gt_entries} sub={`${metrics.verified} verified`} accent="text-term-accent-2" />
              <KPICard label="Approval rate" value={`${metrics.approval_rate}%`} sub={`${metrics.positive} / ${metrics.total_feedback} votes`} accent="text-term-accent" />
            </div>

            {/* Source breakdown */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Gemini calls", value: metrics.gemini_calls, color: "text-term-accent", bg: "bg-term-accent/10", border: "border-term-accent/20" },
                { label: "Memory cache hits", value: metrics.cache_hits, color: "text-term-text-dim", bg: "bg-term-panel-alt", border: "border-term-border" },
                { label: "GT DB hits", value: metrics.gt_hits, color: "text-term-accent-2", bg: "bg-term-accent-2/10", border: "border-term-accent-2/20" },
              ].map((item) => (
                <div key={item.label} className={`rounded-lg p-5 ${item.bg} border ${item.border}`}>
                  <p className="text-xs font-mono text-term-text-dim mb-1">{item.label}</p>
                  <p className={`font-mono text-2xl font-bold ${item.color}`}>{item.value}</p>
                </div>
              ))}
            </div>

            {/* Agent performance chart + table */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-term-panel rounded-lg border border-term-border p-5">
                <p className="text-xs font-mono text-term-text-faint uppercase tracking-widest mb-4">Avg Response Time (ms)</p>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={metrics.agent_stats} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <XAxis dataKey="agent" tick={{ fontSize: 11, fill: themeColors.textFaint }} stroke={themeColors.border} />
                    <YAxis tick={{ fontSize: 10, fill: themeColors.textFaint }} stroke={themeColors.border} />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12, borderRadius: 6,
                        background: themeColors.panel, border: `1px solid ${themeColors.border}`,
                        color: themeColors.textFaint,
                      }}
                      formatter={(v) => [`${v}ms`, "Avg"]}
                    />
                    <Bar dataKey="avg_ms" radius={[4, 4, 0, 0]}>
                      {metrics.agent_stats.map((entry) => (
                        <Cell key={entry.agent} fill={AGENT_COLOR[entry.agent] ?? themeColors.textFaint} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-term-panel rounded-lg border border-term-border p-5">
                <p className="text-xs font-mono text-term-text-faint uppercase tracking-widest mb-4">Agent call breakdown</p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-term-border-faint text-[11px] font-mono text-term-text-faint uppercase tracking-wide">
                      <th className="text-left pb-2 font-medium">Agent</th>
                      <th className="text-right pb-2 font-medium">Total</th>
                      <th className="text-right pb-2 font-medium">Gemini</th>
                      <th className="text-right pb-2 font-medium">Cache</th>
                      <th className="text-right pb-2 font-medium">GT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.agent_stats.map((s) => (
                      <tr key={s.agent} className="border-b border-term-border-faint">
                        <td className="py-2">
                          <span className="font-medium font-mono capitalize" style={{ color: AGENT_COLOR[s.agent] }}>{s.agent}</span>
                        </td>
                        <td className="text-right py-2 font-mono text-xs text-term-text-dim">{s.total_calls}</td>
                        <td className="text-right py-2 font-mono text-xs text-term-accent">{s.gemini_calls}</td>
                        <td className="text-right py-2 font-mono text-xs text-term-text-dim">{s.cache_hits}</td>
                        <td className="text-right py-2 font-mono text-xs text-term-accent-2">{s.gt_hits}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── Ground Truth DB ───────────────────────────────────────────────── */}
        {activeSection === "groundtruth" && (
          <div className="space-y-6">
            <div className="flex items-end justify-between">
              <div>
                <h1 className="font-display text-2xl font-semibold text-term-text mb-1">Ground Truth DB</h1>
                <p className="text-sm text-term-text-dim">Human-verified agent responses. {metrics?.approval_threshold ?? 3} positive signals to verify.</p>
              </div>
              <button onClick={loadGT} className="text-xs font-mono text-term-text-dim border border-term-border rounded-lg px-3 py-1.5 hover:bg-term-panel-alt transition-colors">
                Refresh
              </button>
            </div>

            {/* Filters */}
            <div className="flex gap-3 flex-wrap">
              <input
                value={gtSearch}
                onChange={(e) => setGtSearch(e.target.value)}
                placeholder="Filter by ticker…"
                className="rounded-lg border border-term-border bg-term-panel text-term-text px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-term-accent placeholder:text-term-text-faint"
              />
              <select
                value={gtAgent}
                onChange={(e) => setGtAgent(e.target.value)}
                className="rounded-lg border border-term-border bg-term-panel text-term-text px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-term-accent"
              >
                <option value="">All agents</option>
                {["xavi", "iniesta", "busquets", "messi"].map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm font-mono text-term-text-dim cursor-pointer">
                <input type="checkbox" checked={gtVerifiedOnly} onChange={(e) => setGtVerifiedOnly(e.target.checked)} className="accent-term-accent" />
                Verified only
              </label>
            </div>

            {/* GT table */}
            <div className="bg-term-panel rounded-lg border border-term-border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-term-panel-alt border-b border-term-border">
                  <tr className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">
                    <th className="text-left px-4 py-3 font-medium">ID</th>
                    <th className="text-left px-4 py-3 font-medium">Ticker</th>
                    <th className="text-left px-4 py-3 font-medium">Agent</th>
                    <th className="text-left px-4 py-3 font-medium">Verdict</th>
                    <th className="text-center px-4 py-3 font-medium">👍</th>
                    <th className="text-center px-4 py-3 font-medium">👎</th>
                    <th className="text-center px-4 py-3 font-medium">Verified</th>
                    <th className="text-right px-4 py-3 font-medium">Time</th>
                    <th className="text-right px-4 py-3 font-medium">Updated</th>
                    <th className="text-right px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {gtEntries.length === 0 && (
                    <tr><td colSpan={10} className="text-center py-10 text-term-text-faint text-sm font-mono">No entries yet — run analyses and approve responses to build the Ground Truth DB.</td></tr>
                  )}
                  {gtEntries.map((entry) => (
                    <>
                      <tr key={entry.id} className="border-b border-term-border-faint hover:bg-term-panel-alt transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-term-text-faint">{entry.id}</td>
                        <td className="px-4 py-3 font-mono text-sm font-semibold text-term-text">{entry.ticker}</td>
                        <td className="px-4 py-3">
                          <span className="text-sm font-mono font-medium capitalize" style={{ color: AGENT_COLOR[entry.agent] }}>{entry.agent}</span>
                        </td>
                        <td className="px-4 py-3"><VerdictBadge verdict={entry.verdict} /></td>
                        <td className="px-4 py-3 text-center font-mono text-sm text-term-accent-2">{entry.approval_count}</td>
                        <td className="px-4 py-3 text-center font-mono text-sm text-term-danger">{entry.rejection_count}</td>
                        <td className="px-4 py-3 text-center">
                          {entry.is_verified ? <span className="text-term-accent-2 text-sm">✓</span> : <span className="text-term-text-faint text-sm">—</span>}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-term-text-dim">
                          {entry.response_time_ms != null ? `${entry.response_time_ms}ms` : "—"}
                        </td>
                        <td className="px-4 py-3 text-right text-xs font-mono text-term-text-faint">{entry.updated_at?.slice(0, 16)}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => setExpandedMemo(expandedMemo === entry.id ? null : entry.id)}
                              className="text-[11px] font-mono text-term-accent hover:underline"
                            >
                              {expandedMemo === entry.id ? "Hide" : "Memo"}
                            </button>
                            <button onClick={() => deleteEntry(entry.id)} className="text-[11px] font-mono text-term-danger hover:underline">Delete</button>
                          </div>
                        </td>
                      </tr>
                      {expandedMemo === entry.id && (
                        <tr key={`${entry.id}-memo`} className="bg-term-panel-alt">
                          <td colSpan={10} className="px-6 py-4">
                            <pre className="text-xs text-term-text-dim whitespace-pre-wrap font-mono leading-relaxed max-h-60 overflow-y-auto">{entry.memo}</pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Activity ──────────────────────────────────────────────────────── */}
        {activeSection === "activity" && metrics && (
          <div className="space-y-6">
            <h1 className="font-display text-2xl font-semibold text-term-text">Activity Feed</h1>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-term-panel rounded-lg border border-term-border p-5">
                <p className="text-xs font-mono text-term-text-faint uppercase tracking-widest mb-4">Recent calls</p>
                <div className="space-y-2">
                  {metrics.recent_calls.map((c, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5 border-b border-term-border-faint last:border-0">
                      <span className="font-mono text-xs font-semibold text-term-text w-14 shrink-0">{c.ticker}</span>
                      <span className="text-xs font-mono capitalize flex-1" style={{ color: AGENT_COLOR[c.agent] }}>{c.agent}</span>
                      <SourceBadge source={c.source} />
                      <span className="font-mono text-[11px] text-term-text-faint w-16 text-right">{c.response_time_ms}ms</span>
                      <span className="text-[10px] font-mono text-term-text-faint w-32 text-right shrink-0">{c.created_at?.slice(5, 16)}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-term-panel rounded-lg border border-term-border p-5">
                <p className="text-xs font-mono text-term-text-faint uppercase tracking-widest mb-4">Recent feedback</p>
                <div className="space-y-2">
                  {metrics.recent_feedback.length === 0 && (
                    <p className="text-sm font-mono text-term-text-faint text-center py-4">No feedback yet — use 👍/👎 in the AI sidebar.</p>
                  )}
                  {metrics.recent_feedback.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5 border-b border-term-border-faint last:border-0">
                      <span className="font-mono text-xs font-semibold text-term-text w-14 shrink-0">{f.ticker}</span>
                      <span className="text-xs font-mono capitalize flex-1" style={{ color: AGENT_COLOR[f.agent] }}>{f.agent}</span>
                      <span className="text-base">{f.vote === "positive" ? "👍" : "👎"}</span>
                      {f.comment && <span className="text-[11px] font-mono text-term-text-faint truncate max-w-[100px]">"{f.comment}"</span>}
                      <span className="text-[10px] font-mono text-term-text-faint w-32 text-right shrink-0">{f.created_at?.slice(5, 16)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── API Reference ─────────────────────────────────────────────────── */}
        {activeSection === "api" && (
          <div className="space-y-6">
            <div className="flex items-end justify-between">
              <div>
                <h1 className="font-display text-2xl font-semibold text-term-text mb-1">API Reference</h1>
                <p className="text-sm text-term-text-dim">All Cardinal endpoints. Full interactive docs at <a href={`${API_BASE}/docs`} target="_blank" className="text-term-accent hover:underline">{API_BASE}/docs ↗</a></p>
              </div>
            </div>
            <div className="bg-term-panel rounded-lg border border-term-border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-term-panel-alt border-b border-term-border">
                  <tr className="text-[11px] font-mono text-term-text-faint uppercase tracking-wide">
                    <th className="text-left px-5 py-3 font-medium">Method</th>
                    <th className="text-left px-5 py-3 font-medium">Path</th>
                    <th className="text-left px-5 py-3 font-medium">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {ENDPOINTS.map((ep, i) => (
                    <tr key={i} className="border-b border-term-border-faint hover:bg-term-panel-alt transition-colors">
                      <td className="px-5 py-3">
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded font-mono ${
                          ep.method === "GET" ? "bg-term-accent-2/10 text-term-accent-2"
                          : ep.method === "POST" ? "bg-term-accent/10 text-term-accent"
                          : "bg-term-danger/10 text-term-danger"
                        }`}>{ep.method}</span>
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-term-text">{ep.path}</td>
                      <td className="px-5 py-3 text-sm font-mono text-term-text-dim">{ep.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}