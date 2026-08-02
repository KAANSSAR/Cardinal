"""
Messi — Cardinal's Synthesis Agent and Portfolio Manager.

Named after Lionel Messi: the one who takes everyone else's work and
delivers the decisive action. He doesn't need to see the full game —
he reads what Xavi, Iniesta, and Busquets have done and makes the
final call.

Input:  The three analyst memos (Xavi + Iniesta + Busquets)
Output: One-paragraph buy / hold / sell verdict combining all three lenses

Architecture note: Messi is the only agent that reads other agents'
outputs rather than raw Cardinal data. He still cannot modify anything —
he receives the three memos as read-only text and synthesises them.
"""

from __future__ import annotations

from cardinal.agents.gemini_client import generate


# ── System prompt ─────────────────────────────────────────────────────────────

MESSI_SYSTEM_PROMPT = """
You are Messi, Cardinal's Synthesis Agent — the Portfolio Manager who makes the final call.

You have received three analyst memos from your team:
- Xavi (Fundamental Analyst): evaluated the DCF valuation and comparable companies
- Iniesta (Quantitative Analyst): evaluated momentum signals, Sharpe, beta, and technical positioning
- Busquets (Strategy Reviewer): evaluated the algorithmic backtest results

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. You may ONLY draw conclusions from the three analyst memos provided in [ANALYST MEMOS] below.
2. You cannot introduce external data, market views, or opinions not present in the memos.
3. Never give personalised financial advice or recommend position sizes.
4. If the user asks about something not covered in the memos, say: "That information wasn't covered in this analysis."
5. You are synthesising your team's work — be decisive, not wishy-washy.

OUTPUT FORMAT:
Produce exactly two sections:
**Synthesis Verdict [BUY / HOLD / SELL]:** A single decisive paragraph (4-6 sentences) that:
  - Opens with a clear BUY, HOLD, or SELL call and a one-line rationale
  - Explains how the fundamental, quant, and backtest signals align or conflict
  - Notes the single most important risk or caveat
  - Closes with a specific condition that would change the verdict

**Confidence: [HIGH / MODERATE / LOW]** — One sentence explaining why you chose this confidence level (e.g. conflicting signals, low trade count, elevated vol, etc.)

Keep the total response under 220 words. Write like a PM delivering a final investment committee decision — decisive, clear, accountable.
""".strip()


# ── Snapshot builder ──────────────────────────────────────────────────────────

def build_synthesis_snapshot(
    ticker: str,
    xavi_memo: str,
    iniesta_memo: str,
    busquets_memo: str,
) -> str:
    """
    Combine the three analyst memos into a single synthesis snapshot.
    Messi reads memos — not raw data — which is intentional: he synthesises
    the team's interpretations, not the underlying numbers directly.
    """
    return "\n\n".join([
        f"Ticker: {ticker}",
        "=== XAVI (Fundamental Analyst) ===",
        xavi_memo.strip(),
        "=== INIESTA (Quantitative Analyst) ===",
        iniesta_memo.strip(),
        "=== BUSQUETS (Strategy Reviewer) ===",
        busquets_memo.strip(),
    ])


# ── Agent entry point ─────────────────────────────────────────────────────────

def run_messi(
    ticker: str,
    xavi_memo: str,
    iniesta_memo: str,
    busquets_memo: str,
    user_question: str | None = None,
) -> str:
    """
    Run the Messi synthesis agent.

    Receives the three analyst memos directly — no additional data fetching.
    Messi synthesises the team's work and delivers the final verdict.
    """
    snapshot = build_synthesis_snapshot(ticker, xavi_memo, iniesta_memo, busquets_memo)
    parts = [f"[ANALYST MEMOS]\n{snapshot}"]

    if user_question:
        parts.append(f"[USER QUESTION]\n{user_question}")
    else:
        parts.append(
            "[TASK]\nReview all three analyst memos above and deliver your final "
            "portfolio manager verdict for this ticker."
        )

    prompt = "\n\n".join(parts)
    return generate(prompt, system_prompt=MESSI_SYSTEM_PROMPT, max_output_tokens=512)