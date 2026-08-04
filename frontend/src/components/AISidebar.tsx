import { useRef, useState } from "react";
import {
  fetchMessi,
  type DCFAssumptions,
  type MessiResponse,
  type BacktestStrategy,
} from "../lib/api";

// ── Typing animation ──────────────────────────────────────────────────────────

function TypingDots() {
  return (
    <span className="inline-flex gap-1 items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-term-text-faint animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.8s" }}
        />
      ))}
    </span>
  );
}

// ── Thinking cloud ────────────────────────────────────────────────────────────

function ThinkingCloud({ content }: { content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 border border-term-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-term-panel-alt transition-colors"
      >
        <span className="text-[11px] text-term-text-faint">{open ? "▾" : "▸"}</span>
        <span className="text-[11px] text-term-text-dim font-medium font-mono">Data snapshot sent to agent</span>
      </button>
      {open && (
        <pre className="px-3 pb-3 text-[10px] text-term-text-dim leading-relaxed whitespace-pre-wrap font-mono bg-term-panel-alt border-t border-term-border-faint max-h-48 overflow-y-auto">
          {content}
        </pre>
      )}
    </div>
  );
}

// ── Feedback bar ──────────────────────────────────────────────────────────────

const POSITIVE_KEYWORDS = ["great", "perfect", "correct", "accurate", "spot on", "exactly", "well done", "looks good", "good", "awesome", "brilliant", "nice"];

function isPositiveText(text: string): boolean {
  const lower = text.toLowerCase().trim();
  return POSITIVE_KEYWORDS.some((kw) => lower.includes(kw));
}

interface FeedbackBarProps {
  ticker: string;
  agent: string;
  paramsHash: string;
  approvals: number;
  rejections: number;
  isVerified: boolean;
  responseTimeMs: number;
  onVote: (vote: "positive" | "negative") => void;
}

function FeedbackBar({ approvals, isVerified, responseTimeMs, onVote }: FeedbackBarProps) {
  const [voted, setVoted] = useState<"positive" | "negative" | null>(null);
  const threshold = 3;

  function handleVote(v: "positive" | "negative") {
    if (voted) return;
    setVoted(v);
    onVote(v);
  }

  return (
    <div className="mt-4 pt-3 border-t border-term-border-faint flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => handleVote("positive")}
          disabled={!!voted}
          title="Helpful"
          className={`text-base transition-opacity ${voted === "positive" ? "opacity-100" : voted ? "opacity-30" : "hover:scale-110"}`}
        >
          👍
        </button>
        <button
          onClick={() => handleVote("negative")}
          disabled={!!voted}
          title="Not helpful"
          className={`text-base transition-opacity ${voted === "negative" ? "opacity-100" : voted ? "opacity-30" : "hover:scale-110"}`}
        >
          👎
        </button>
        {isVerified ? (
          <span className="text-[10px] font-mono text-term-accent-2 font-medium">✓ Ground truth verified</span>
        ) : (
          <span className="text-[10px] font-mono text-term-text-faint">{approvals}/{threshold} approvals</span>
        )}
      </div>
      <span className="text-[10px] text-term-text-faint font-mono">{responseTimeMs > 0 ? `${responseTimeMs}ms` : ""}</span>
    </div>
  );
}

// ── Memo renderer ─────────────────────────────────────────────────────────────

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? <strong key={i} className="text-term-text font-semibold">{part}</strong> : part
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
            <span className="text-[10px] font-bold font-mono text-term-text-faint uppercase tracking-widest">{cleanHeader}</span>
            {tagMatch && (
              <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border ${
                tagMatch[1].includes("BUY") ? "border-term-accent-2 text-term-accent-2 bg-term-accent-2/10"
                : tagMatch[1].includes("SELL") ? "border-term-danger text-term-danger bg-term-danger/10"
                : tagMatch[1].includes("HIGH") ? "border-term-accent-2 text-term-accent-2 bg-term-accent-2/10"
                : tagMatch[1].includes("LOW") ? "border-term-accent text-term-accent bg-term-accent/10"
                : "border-term-border-light text-term-text-dim bg-term-panel-alt"
              }`}>{tagMatch[1]}</span>
            )}
          </div>
          {rest && <p className="text-sm text-term-text-dim mt-1 leading-relaxed">{renderInline(rest)}</p>}
        </div>
      );
      return;
    }
    const numMatch = line.match(/^(\d+)\.\s+(.+)$/);
    if (numMatch) {
      elements.push(
        <div key={i} className="flex gap-2.5 text-sm text-term-text-dim mt-1.5">
          <span className="font-mono text-term-accent shrink-0 font-semibold">{numMatch[1]}.</span>
          <span className="leading-relaxed">{renderInline(numMatch[2])}</span>
        </div>
      );
      return;
    }
    elements.push(<p key={i} className="text-sm text-term-text-dim leading-relaxed mt-1">{renderInline(line)}</p>);
  });
  return <div>{elements}</div>;
}

// ── Per-agent empty states ────────────────────────────────────────────────────

const AGENT_DESCRIPTIONS: Record<string, { title: string; body: string }> = {
  xavi: { title: "Xavi — Fundamental Analyst", body: "Reviews the DCF model — intrinsic value, terminal value dependency, WACC, and peer multiples — and writes a structured investment memo with bull case, bear case, and key risks." },
  iniesta: { title: "Iniesta — Quant Analyst", body: "Analyses momentum across 20d, 60d, and 252d windows, Sharpe ratios, beta, the full volatility surface, RSI, and Bollinger bands to deliver a directional signal bias with timing commentary." },
  busquets: { title: "Busquets — Strategy Reviewer", body: "Reviews the backtest P&L curve, Sharpe, max drawdown, and win rate to assess whether the selected algo strategy has genuine edge — or just looks good on paper." },
  messi: { title: "Messi — Portfolio Manager", body: "Reads the full team's analysis and delivers the final BUY / HOLD / SELL verdict. After the analysis runs, chat with Messi to interrogate any aspect of the data." },
};

// ── Chat types ────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  isPositive?: boolean;
}

// ── Tab config ────────────────────────────────────────────────────────────────
// Agent identity colors are fixed (not tied to the Amber/Cyan/Green terminal
// theme) — same reasoning as the homepage lens dots: these code "which agent",
// not "which terminal skin".

type AgentTab = "xavi" | "iniesta" | "busquets" | "messi";

const TABS: { key: AgentTab; label: string; role: string; color: string }[] = [
  { key: "xavi", label: "Xavi", role: "Fundamental", color: "border-teal text-teal" },
  { key: "iniesta", label: "Iniesta", role: "Quant", color: "border-blue text-blue" },
  { key: "busquets", label: "Busquets", role: "Backtest", color: "border-purple text-purple" },
  { key: "messi", label: "Messi", role: "Synthesis", color: "border-amber-500 text-amber-500" },
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
  const [approvals, setApprovals] = useState({ approval_count: 0, rejection_count: 0, is_verified: false });

  // Chat state
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
    setApprovals({ approval_count: 0, rejection_count: 0, is_verified: false });
    try {
      const result = await fetchMessi({ ticker, strategy, ...assumptions });
      setData(result);
      setApprovals({
        approval_count: result.synthesis_approval_count,
        rejection_count: result.synthesis_rejection_count,
        is_verified: result.synthesis_is_verified,
      });
      setActiveTab("messi");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback(vote: "positive" | "negative", comment?: string) {
    if (!data) return;
    try {
      const res = await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker, agent: "messi",
          params_hash: data.synthesis_params_hash,
          vote, comment: comment ?? null,
        }),
      });
      const json = await res.json();
      setApprovals({ approval_count: json.approval_count, rejection_count: json.rejection_count, is_verified: json.is_verified });
    } catch { /* silent */ }
  }

  async function sendChatMessage(message: string, historyOverride?: ChatMessage[]) {
    if (!message.trim() || !data) return;
    const userMsg: ChatMessage = { role: "user", content: message.trim() };
    const hist = historyOverride ?? chatHistory;
    const newHistory = [...hist, userMsg];
    setChatHistory(newHistory);
    setChatInput("");
    setChatLoading(true);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);

    // Detect positive text for auto-feedback
    if (isPositiveText(message)) {
      submitFeedback("positive", message);
    }

    try {
      const res = await fetch(`${API_BASE}/agent/messi/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          xavi_memo: data.xavi_memo, iniesta_memo: data.iniesta_memo,
          busquets_memo: data.busquets_memo, synthesis_memo: data.synthesis_memo,
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

  // Edit a sent message — clears everything after it
  function startEdit(idx: number) {
    setEditingIndex(idx);
    setEditValue(chatHistory[idx].content);
  }

  function confirmEdit(idx: number) {
    if (!editValue.trim()) return;
    const trimmed = chatHistory.slice(0, idx); // remove from idx onwards
    setChatHistory(trimmed);
    setEditingIndex(null);
    sendChatMessage(editValue, trimmed);
    setEditValue("");
  }

  const memo = getMemo();
  const isCached = (key: AgentTab) => data?.cached_agents?.includes(key) ?? false;
  const desc = AGENT_DESCRIPTIONS[activeTab];

  return (
    <div className="flex flex-col h-full w-full bg-term-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-term-border-faint shrink-0">
        <div>
          <p className="font-display text-sm font-semibold text-term-text">Cardinal AI</p>
          <p className="text-[11px] text-term-text-faint font-mono">{ticker}</p>
        </div>
        <div className="flex items-center gap-2">
          {data?.news_used && <span className="text-[10px] font-mono font-medium text-term-accent bg-term-accent/10 px-2 py-0.5 rounded-full border border-term-accent/30">+ news</span>}
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-term-text-faint hover:bg-term-panel-alt hover:text-term-text-dim transition-colors">✕</button>
        </div>
      </div>

      {/* Agent tabs */}
      <div className="flex border-b border-term-border-faint shrink-0 px-1 pt-1">
        {TABS.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`relative flex flex-col items-center flex-1 py-1.5 text-[10px] border-b-2 -mb-px transition-colors ${activeTab === tab.key ? tab.color : "border-transparent text-term-text-faint hover:text-term-text-dim"}`}
          >
            <span className="font-semibold text-[11px] font-mono">{tab.label}</span>
            <span className="opacity-60 font-mono">{tab.role}</span>
            {isCached(tab.key) && <span className="absolute top-1 right-2 w-1.5 h-1.5 rounded-full bg-term-accent-2" title="From cache" />}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {/* Empty state */}
        {!data && !loading && !error && (
          <div className="flex flex-col items-center text-center gap-3 py-6">
            <div className="w-10 h-10 rounded-xl bg-term-panel-alt border border-term-border flex items-center justify-center">
              <span className="text-sm font-bold text-term-text-dim font-mono">
                {activeTab === "messi" ? "M" : activeTab === "xavi" ? "X" : activeTab === "iniesta" ? "I" : "B"}
              </span>
            </div>
            <p className="text-sm font-semibold text-term-text">{desc.title}</p>
            <p className="text-xs text-term-text-faint leading-relaxed max-w-[240px]">{desc.body}</p>
            <button onClick={handleRunAnalysis} className="mt-2 px-5 py-2 rounded-lg bg-term-accent text-term-bg font-mono font-bold text-sm uppercase tracking-wide hover:opacity-90 transition-opacity">
              Run full analysis
            </button>
          </div>
        )}

        {/* Loading — per-agent animated state */}
        {loading && (
          <div className="flex flex-col items-center justify-center flex-1 gap-4">
            <div className="w-full space-y-2">
              {(["Xavi", "Iniesta", "Busquets", "Messi"] as const).map((name) => (
                <div key={name} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-term-panel-alt border border-term-border-faint">
                  <div className="w-6 h-6 rounded-full bg-term-panel border border-term-border flex items-center justify-center">
                    <span className="text-[9px] font-bold text-term-text-dim font-mono">{name[0]}</span>
                  </div>
                  <span className="text-xs text-term-text-dim font-mono flex-1">{name}</span>
                  <TypingDots />
                </div>
              ))}
            </div>
            <p className="text-xs font-mono text-term-text-faint">Running the full team…</p>
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg bg-term-danger/10 border border-term-danger/30 px-4 py-3 text-sm text-term-danger">{error}</div>
        )}

        {/* Memo + thinking cloud + feedback */}
        {memo && !loading && (
          <div>
            {isCached(activeTab) && activeTab !== "messi" && (
              <div className="mb-3 flex items-center gap-1.5 text-[11px] font-mono text-term-accent-2">
                <span className="w-1.5 h-1.5 rounded-full bg-term-accent-2 inline-block" />
                Served from cache
              </div>
            )}
            <MemoDisplay memo={memo} />
            {/* Thinking cloud — only for fresh (non-cached) non-Messi tabs */}
            {activeTab !== "messi" && !isCached(activeTab) && (
              <ThinkingCloud content={`[Data snapshot sent to ${activeTab}]\n\n(run individual agent endpoint to see snapshot)`} />
            )}
            {/* Feedback bar */}
            <FeedbackBar
              ticker={ticker}
              agent={activeTab}
              paramsHash={data?.synthesis_params_hash ?? ""}
              approvals={activeTab === "messi" ? approvals.approval_count : 0}
              rejections={activeTab === "messi" ? approvals.rejection_count : 0}
              isVerified={activeTab === "messi" ? approvals.is_verified : false}
              responseTimeMs={activeTab === "messi" ? (data?.response_time_ms ?? 0) : 0}
              onVote={(v) => submitFeedback(v)}
            />
          </div>
        )}

        {/* Messi chat */}
        {data && !loading && activeTab === "messi" && (
          <div className="mt-2 border-t border-term-border-faint pt-4 flex flex-col gap-3">
            <p className="text-[10px] font-bold font-mono text-term-text-faint uppercase tracking-widest">Ask Messi</p>

            {chatHistory.length > 0 && (
              <div className="flex flex-col gap-3">
                {chatHistory.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    {msg.role === "user" && editingIndex === i ? (
                      <div className="flex gap-2 max-w-[85%]">
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && confirmEdit(i)}
                          autoFocus
                          className="flex-1 rounded-lg border border-term-accent px-3 py-2 text-sm focus:outline-none bg-term-panel text-term-text"
                        />
                        <button onClick={() => confirmEdit(i)} className="px-2 py-1 rounded-lg bg-term-accent text-term-bg text-xs font-bold">↵</button>
                        <button onClick={() => setEditingIndex(null)} className="px-2 py-1 rounded-lg bg-term-panel-alt border border-term-border text-term-text-dim text-xs">✕</button>
                      </div>
                    ) : (
                      <div
                        className={`group max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed relative ${msg.role === "user" ? "bg-term-accent text-term-bg cursor-pointer" : "bg-term-panel-alt text-term-text border border-term-border-faint"}`}
                        onClick={() => msg.role === "user" && startEdit(i)}
                        title={msg.role === "user" ? "Click to edit" : undefined}
                      >
                        {msg.content}
                        {msg.role === "user" && (
                          <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 text-[9px] bg-term-panel border border-term-border text-term-text-dim rounded px-1 transition-opacity">edit</span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-term-panel-alt border border-term-border-faint rounded-xl px-3 py-2"><TypingDots /></div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}

            <div className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendChatMessage(chatInput)}
                placeholder="Ask about the analysis…"
                disabled={chatLoading}
                className="flex-1 rounded-lg border border-term-border px-3 py-2 text-sm focus:outline-none focus:border-term-accent transition-colors disabled:opacity-50 bg-term-panel text-term-text placeholder:text-term-text-faint"
              />
              <button
                onClick={() => sendChatMessage(chatInput)}
                disabled={chatLoading || !chatInput.trim()}
                className="px-3 py-2 rounded-lg bg-term-accent text-term-bg font-bold text-sm hover:opacity-90 transition-opacity disabled:opacity-40"
              >→</button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      {data && !loading && (
        <div className="px-4 py-3 border-t border-term-border-faint shrink-0">
          <p className="text-[10px] font-mono text-term-text-faint text-center mb-2">
            {data.cached_agents.length > 0 ? `${data.cached_agents.join(", ")} from cache` : "All agents ran fresh"}
            {data.news_used && " · news included"}
            {data.response_time_ms > 0 && ` · ${data.response_time_ms}ms`}
          </p>
          <button onClick={handleRunAnalysis} className="w-full py-2 rounded-xl bg-term-accent text-term-bg font-mono font-bold text-sm uppercase tracking-wide hover:opacity-90 transition-opacity">
            Re-run analysis
          </button>
        </div>
      )}
    </div>
  );
}