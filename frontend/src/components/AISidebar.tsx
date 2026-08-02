import { useRef, useState } from "react";
import {
  fetchMessi,
  type DCFAssumptions,
  type MessiResponse,
  type BacktestStrategy,
} from "../lib/api";

// ── Memo renderer ─────────────────────────────────────────────────────────────

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1
      ? <strong key={i} className="text-dark-text font-semibold">{part}</strong>
      : part
  );
}

function MemoDisplay({ memo }: { memo: string }) {
  if (!memo) return null;
  const lines = memo.split("\n").filter((l) => l.trim());
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    const headerMatch = line.match(/^\*\*([^*]+)\*\*:?\s*(.*)$/);
    if (headerMatch) {
      const [, header, rest] = headerMatch;
      const tagMatch = header.match(/\[([A-Z/ ]+)\]/);
      const cleanHeader = header.replace(/\s*\[[A-Z/ ]+\]/, "").trim();
      elements.push(
        <div key={i} className="mt-4 first:mt-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-bold text-slate uppercase tracking-widest">{cleanHeader}</span>
            {tagMatch && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                tagMatch[1].includes("BUY") ? "border-green-500 text-green-600 bg-green-50"
                : tagMatch[1].includes("SELL") ? "border-red-500 text-red-600 bg-red-50"
                : tagMatch[1].includes("HIGH") ? "border-green-500 text-green-600 bg-green-50"
                : tagMatch[1].includes("LOW") ? "border-amber-500 text-amber-600 bg-amber-50"
                : "border-teal text-teal bg-teal/5"
              }`}>{tagMatch[1]}</span>
            )}
          </div>
          {rest && <p className="text-sm text-slate mt-1 leading-relaxed">{renderInline(rest)}</p>}
        </div>
      );
      return;
    }
    const numMatch = line.match(/^(\d+)\.\s+(.+)$/);
    if (numMatch) {
      elements.push(
        <div key={i} className="flex gap-2.5 text-sm text-slate mt-1.5">
          <span className="font-mono text-teal shrink-0 font-semibold">{numMatch[1]}.</span>
          <span className="leading-relaxed">{renderInline(numMatch[2])}</span>
        </div>
      );
      return;
    }
    elements.push(
      <p key={i} className="text-sm text-slate leading-relaxed mt-1">{renderInline(line)}</p>
    );
  });

  return <div>{elements}</div>;
}

// ── Per-agent empty states ────────────────────────────────────────────────────

const AGENT_DESCRIPTIONS: Record<string, { title: string; body: string }> = {
  xavi: {
    title: "Xavi — Fundamental Analyst",
    body: "Reviews the DCF model — intrinsic value, terminal value dependency, WACC, and peer multiples — then writes a structured investment memo with bull case, bear case, and key risks.",
  },
  iniesta: {
    title: "Iniesta — Quant Analyst",
    body: "Analyses the momentum signals across 20d, 60d, and 252d windows, Sharpe ratios, beta, the full volatility surface, RSI, and Bollinger bands to deliver a directional signal bias.",
  },
  busquets: {
    title: "Busquets — Strategy Reviewer",
    body: "Reviews the backtest P&L curve, Sharpe, max drawdown, and win rate to assess whether the selected strategy has genuine edge — or just noise.",
  },
  messi: {
    title: "Messi — Portfolio Manager",
    body: "Reads the full team's analysis and delivers the final BUY / HOLD / SELL verdict. After the analysis runs, you can chat with Messi about any aspect of the data.",
  },
};

// ── Chat types ────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── Tab config ────────────────────────────────────────────────────────────────

type AgentTab = "xavi" | "iniesta" | "busquets" | "messi";

const TABS: { key: AgentTab; label: string; role: string; color: string }[] = [
  { key: "xavi", label: "Xavi", role: "Fundamental", color: "border-teal text-teal" },
  { key: "iniesta", label: "Iniesta", role: "Quant", color: "border-blue text-blue" },
  { key: "busquets", label: "Busquets", role: "Backtest", color: "border-purple text-purple" },
  { key: "messi", label: "Messi", role: "Synthesis", color: "border-amber-500 text-amber-600" },
];

// ── Main sidebar ──────────────────────────────────────────────────────────────

interface Props {
  ticker: string;
  assumptions: Partial<DCFAssumptions>;
  strategy: BacktestStrategy;
  onClose: () => void;
}

export default function AISidebar({ ticker, assumptions, strategy, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<AgentTab>("messi");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<MessiResponse | null>(null);

  // Chat state (Messi only)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  function getMemo(): string | null {
    if (!data) return null;
    switch (activeTab) {
      case "xavi": return data.xavi_memo;
      case "iniesta": return data.iniesta_memo;
      case "busquets": return data.busquets_memo;
      case "messi": return data.synthesis_memo;
    }
  }

  async function handleRunAnalysis() {
    setLoading(true);
    setError(null);
    setChatHistory([]);
    try {
      const result = await fetchMessi({ ticker, strategy, ...assumptions });
      setData(result);
      setActiveTab("messi");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendChat() {
    if (!chatInput.trim() || !data) return;
    const userMsg: ChatMessage = { role: "user", content: chatInput.trim() };
    const newHistory = [...chatHistory, userMsg];
    setChatHistory(newHistory);
    setChatInput("");
    setChatLoading(true);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);

    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
      const res = await fetch(`${API_BASE}/agent/messi/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          xavi_memo: data.xavi_memo,
          iniesta_memo: data.iniesta_memo,
          busquets_memo: data.busquets_memo,
          synthesis_memo: data.synthesis_memo,
          message: userMsg.content,
          history: newHistory.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const json = await res.json();
      const reply: ChatMessage = { role: "assistant", content: json.reply ?? json.detail ?? "Error" };
      setChatHistory((h) => [...h, reply]);
    } catch {
      setChatHistory((h) => [...h, { role: "assistant", content: "Something went wrong — try again." }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  const memo = getMemo();
  const isCached = (key: AgentTab) => data?.cached_agents?.includes(key) ?? false;
  const desc = AGENT_DESCRIPTIONS[activeTab];

  return (
    <div className="flex flex-col h-full w-full">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 shrink-0">
        <div>
          <p className="font-display text-sm font-semibold text-dark-text">Cardinal AI</p>
          <p className="text-[11px] text-slate font-mono">{ticker}</p>
        </div>
        <div className="flex items-center gap-2">
          {data?.news_used && (
            <span className="text-[10px] font-medium text-teal bg-teal/10 px-2 py-0.5 rounded-full border border-teal/20">
              + news
            </span>
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-slate hover:bg-slate-100 transition-colors"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Agent tabs */}
      <div className="flex border-b border-slate-100 shrink-0 px-1 pt-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`relative flex flex-col items-center flex-1 py-1.5 text-[10px] border-b-2 -mb-px transition-colors ${
              activeTab === tab.key ? tab.color : "border-transparent text-slate hover:text-slate-dark"
            }`}
          >
            <span className="font-semibold text-[11px]">{tab.label}</span>
            <span className="opacity-60">{tab.role}</span>
            {isCached(tab.key) && (
              <span className="absolute top-1 right-2 w-1.5 h-1.5 rounded-full bg-teal" title="From cache" />
            )}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">

        {/* Empty state — shown when no analysis yet */}
        {!data && !loading && !error && (
          <div className="flex flex-col items-center text-center gap-3 py-6">
            <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
              <span className="text-sm font-bold text-slate font-mono">{activeTab === "messi" ? "M" : activeTab === "xavi" ? "X" : activeTab === "iniesta" ? "I" : "B"}</span>
            </div>
            <p className="text-sm font-semibold text-dark-text">{desc.title}</p>
            <p className="text-xs text-slate leading-relaxed max-w-[240px]">{desc.body}</p>
            <button
              onClick={handleRunAnalysis}
              className="mt-2 px-5 py-2 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-2 transition-colors"
            >
              Run full analysis
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center flex-1 gap-3">
            <div className="w-7 h-7 rounded-full border-2 border-teal border-t-transparent animate-spin" />
            <p className="text-sm text-slate animate-pulse">Running the team…</p>
            <p className="text-[11px] text-slate-light">Xavi → Iniesta → Busquets → Messi</p>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Memo content */}
        {memo && !loading && (
          <div>
            {isCached(activeTab) && activeTab !== "messi" && (
              <div className="mb-3 flex items-center gap-1.5 text-[11px] text-teal">
                <span className="w-1.5 h-1.5 rounded-full bg-teal inline-block" />
                Served from cache
              </div>
            )}
            <MemoDisplay memo={memo} />
          </div>
        )}

        {/* Messi chat — only shown when analysis is done and on Messi tab */}
        {data && !loading && activeTab === "messi" && (
          <div className="mt-2 border-t border-slate-100 pt-4 flex flex-col gap-3">
            <p className="text-[10px] font-bold text-slate uppercase tracking-widest">Ask Messi</p>

            {/* Chat history */}
            {chatHistory.length > 0 && (
              <div className="flex flex-col gap-3">
                {chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-navy text-white"
                        : "bg-slate-100 text-dark-text"
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-slate-100 rounded-xl px-3 py-2">
                      <span className="text-sm text-slate animate-pulse">Messi is thinking…</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}

            {/* Chat input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendChat()}
                placeholder="Ask about the analysis…"
                disabled={chatLoading}
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-teal transition-colors disabled:opacity-50 bg-white"
              />
              <button
                onClick={handleSendChat}
                disabled={chatLoading || !chatInput.trim()}
                className="px-3 py-2 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-2 transition-colors disabled:opacity-40"
              >
                →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer — only shown when analysis has run */}
      {data && !loading && (
        <div className="px-4 py-3 border-t border-slate-100 shrink-0">
          <p className="text-[10px] text-slate-light text-center mb-2">
            {data.cached_agents.length > 0 ? `${data.cached_agents.join(", ")} from cache` : "All agents ran fresh"}
            {data.news_used && " · news included"}
          </p>
          <button
            onClick={handleRunAnalysis}
            className="w-full py-2 rounded-xl bg-navy text-white text-sm font-medium hover:bg-navy-2 transition-colors"
          >
            Re-run analysis
          </button>
        </div>
      )}
    </div>
  );
}