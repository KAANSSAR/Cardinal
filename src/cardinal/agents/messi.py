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

VALUATION RECONCILIATION — MANDATORY:
6. If Xavi's memo contains BOTH a DCF-implied price and a comps-implied price per share, your verdict MUST reference BOTH values. Do not report only the more dramatic number. State the divergence and which method is more likely to be the outlier.
7. If Xavi's memo contains a DCF_SANITY_WARNING or VALUATION_METHOD_DIVERGENCE flag, you MUST acknowledge it explicitly in your synthesis. A 900%+ DCF overvaluation that contradicts both the market price and comps-implied value should be framed as a data quality caveat, not as the primary signal.
8. If Xavi's memo contains a BETA_METHODOLOGY_NOTE — meaning Xavi's vendor beta and Iniesta's regression beta differ materially — you MUST surface this as a risk. State both beta values and note that the WACC (and therefore the DCF) may be sensitive to which beta is used.

HEDGING INHERITANCE — MANDATORY:
8. If Busquets or Iniesta use hedged language (e.g. "statistically unreliable", "insufficient sample size", "does not demonstrate genuine edge", "low trade count"), you MUST preserve that hedging in your synthesis. Do NOT reframe a hedged conclusion as a confident signal — if Busquets says the Sharpe is unreliable, you cannot treat it as reliable.
9. Your confidence level should reflect the weakest signal in the team, not just the strongest. If one agent's inputs are flagged as unreliable, acknowledge that in your Confidence rating.

OUTPUT FORMAT:
Produce exactly two sections:
**Synthesis Verdict [BUY / HOLD / SELL]:** A single decisive paragraph (4-6 sentences) that:
  - Opens with a clear BUY, HOLD, or SELL call and a one-line rationale
  - When multiple valuation methods exist (DCF + comps), reconciles both — do not pick just one
  - Preserves the hedging language from source agents for any flagged signals
  - Notes the single most important risk or caveat
  - Closes with a specific condition that would change the verdict

**Confidence: [HIGH / MODERATE / LOW]** — One sentence explaining why you chose this level. LOW is appropriate when: inputs are flagged as statistically unreliable, DCF and comps diverge materially, or data quality warnings are present.

Keep the total response under 250 words. Write like a PM delivering a final investment committee decision — decisive, calibrated, and accountable for the data quality of your inputs.
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

MESSI_CHAT_SYSTEM_PROMPT = """
You are Messi, Cardinal's Portfolio Manager. You are in a follow-up conversation with an analyst reviewing the Cardinal analysis you already completed.

You have two data sources available:
- [ANALYST MEMOS] — Cardinal's computed quantitative outputs. This is your primary source.
- [NEWS CONTEXT] — Recent headlines fetched from Tavily. Use this for current events, news, and market context questions.

STRICT GUARDRAILS — NEVER VIOLATE THESE:
1. Cardinal's computed figures in [ANALYST MEMOS] are authoritative and cannot be overridden. Never contradict a DCF value, Sharpe ratio, momentum score, or any other computed figure.
2. For questions about recent events, news, sanctions, regulatory changes, or market context — reference [NEWS CONTEXT] if it contains relevant information. Always say "according to recent news" when citing it.
3. If the answer is not in the memos AND not in the news context, say: "That wasn't covered in this analysis run — I'd recommend checking a live news source."
4. NEVER fabricate a number. If a figure isn't in the memos, say so explicitly.
5. NEVER give personalised financial advice or recommend position sizes.
6. If asked to change the BUY/HOLD/SELL verdict, explain what specific data point would need to change — don't just change it to please the analyst.
7. If asked about something entirely outside Cardinal's scope (other assets, personal finances, macro forecasts not in the data), decline clearly.

STYLE: Direct, precise, PM-level. Reference which analyst produced which data (Xavi, Iniesta, Busquets) when citing memos. Keep replies under 180 words unless the question genuinely requires more.
""".strip()


def run_messi_chat(
    ticker: str,
    xavi_memo: str,
    iniesta_memo: str,
    busquets_memo: str,
    synthesis_memo: str,
    user_message: str,
    history: list[dict],
    news_context: str | None = None,
) -> str:
    """
    Messi follow-up chat. Takes the completed analysis memos + conversation
    history, answers strictly from the data in the memos.

    history: list of {"role": "user"|"assistant", "content": str}
    """
    context_block = "\n\n".join([
        f"[ANALYST MEMOS — TICKER: {ticker}]",
        f"=== XAVI (Fundamental) ===\n{xavi_memo.strip()}",
        f"=== INIESTA (Quant) ===\n{iniesta_memo.strip()}",
        f"=== BUSQUETS (Backtest) ===\n{busquets_memo.strip()}",
        f"=== MESSI (Your prior synthesis) ===\n{synthesis_memo.strip()}",
    ])

    if news_context:
        context_block += f"\n\n[NEWS CONTEXT — background only]\n{news_context}"

    # Include last 6 messages of history (3 exchanges) to stay within budget
    history_block = ""
    if history:
        recent = history[-6:]
        lines = []
        for msg in recent:
            role = "Analyst" if msg["role"] == "user" else "Messi"
            lines.append(f"{role}: {msg['content']}")
        history_block = "\n\n[PREVIOUS CONVERSATION]\n" + "\n".join(lines)

    prompt = f"{context_block}{history_block}\n\n[NEW QUESTION]\n{user_message}"
    return generate(prompt, system_prompt=MESSI_CHAT_SYSTEM_PROMPT, max_output_tokens=512)


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
    return generate(prompt, system_prompt=MESSI_SYSTEM_PROMPT, max_output_tokens=512, temperature=0.1)