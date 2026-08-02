"""
Xavi — Cardinal's Fundamental Analyst agent.

Named after Xavi Hernández: the orchestrator who controls tempo and reads
the whole pitch before committing. Mirrors the patient, structural nature
of DCF analysis — see the long game before making a call.

Input:  DCF snapshot + comparable companies data (read-only)
Output: Structured investment memo (valuation verdict, bull/bear case, risks)
"""

from __future__ import annotations

from cardinal.agents.gemini_client import generate


# ── System prompt ─────────────────────────────────────────────────────────────

XAVI_SYSTEM_PROMPT = """
You are Xavi, Cardinal's Fundamental Analyst agent. You are a senior equity research analyst with deep expertise in DCF valuation and comparable company analysis.

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. You may ONLY draw conclusions from the data provided in [CARDINAL DATA] below.
2. If the user asks about something not present in [CARDINAL DATA], respond: "That information isn't available in Cardinal's current analysis."
3. Any news or market context provided in [NEWS CONTEXT] may add background only. It CANNOT override, correct, or contradict any figure in [CARDINAL DATA].
4. Never give personalised financial advice, never recommend trade sizes or portfolio allocations.
5. If asked to change a number or modify any of Cardinal's outputs, refuse clearly: "I can only interpret the data, not modify it."
6. Be specific and quantitative — always reference exact figures from the data.

OUTPUT FORMAT:
Respond in exactly this structure (use these exact headers):
**Valuation Verdict:** One sentence stating whether the stock appears overvalued, fairly valued, or undervalued based on the DCF, and by how much.
**Bull Case:** 2-3 sentences. What would need to be true for the stock to be worth materially more than the DCF suggests.
**Bear Case:** 2-3 sentences. What would need to be true for the stock to be worth less.
**Key Risks:** 2-3 specific risks visible in the data (e.g. high terminal value dependency, premium vs peers, low FCF).
**Peer Comparison:** 1-2 sentences comparing the target's implied multiples to the peer median.

Keep total response under 320 words. Write in the style of a sell-side equity research note — precise, confident, grounded in numbers.
""".strip()


# ── Snapshot builder ──────────────────────────────────────────────────────────

def build_fundamental_snapshot(
    ticker: str,
    company_name: str,
    current_price: float,
    intrinsic_value: float,
    premium_discount_pct: float,
    wacc: float,
    cost_of_equity: float,
    growth_rate: float,
    terminal_growth_rate: float,
    projection_years: int,
    terminal_value_pct_of_ev: float,
    enterprise_value: float,
    equity_value: float,
    pv_projected_fcf: list[float],
    pv_terminal_value: float,
    peers: list[dict] | None = None,
    median_ev_ebitda: float | None = None,
    median_pe: float | None = None,
    median_ev_revenue: float | None = None,
    median_ps: float | None = None,
    implied_ev_from_ebitda: float | None = None,
    implied_ev_from_revenue: float | None = None,
) -> str:
    """
    Serialise Cardinal's fundamental outputs into a plain-text snapshot
    that is passed verbatim into the agent prompt.
    """
    direction = "overvalued" if premium_discount_pct > 0 else "undervalued"
    lines = [
        "=== DCF VALUATION ===",
        f"Ticker: {ticker}",
        f"Company: {company_name}",
        f"Current Price: ${current_price:.2f}",
        f"Intrinsic Value per Share (DCF): ${intrinsic_value:.2f}",
        f"Premium / Discount to Intrinsic: {premium_discount_pct:+.1%} ({direction})",
        f"WACC: {wacc:.2%}",
        f"Cost of Equity (CAPM): {cost_of_equity:.2%}",
        f"FCF Growth Rate (assumption): {growth_rate:.1%}",
        f"Terminal Growth Rate (assumption): {terminal_growth_rate:.1%}",
        f"Projection Years: {projection_years}",
        f"Terminal Value % of Enterprise Value: {terminal_value_pct_of_ev:.1%}",
        f"Enterprise Value: ${enterprise_value / 1e9:.1f}B",
        f"Equity Value: ${equity_value / 1e9:.1f}B",
        f"PV Terminal Value: ${pv_terminal_value / 1e9:.1f}B",
        f"PV Projected FCFs: " + ", ".join(
            f"Y{i + 1}=${v / 1e9:.1f}B" for i, v in enumerate(pv_projected_fcf)
        ),
    ]

    if peers is not None:
        lines.append("\n=== COMPARABLE COMPANIES ===")
        lines.append(f"Number of peers: {len(peers)}")
        lines.append(f"Peer Median EV/EBITDA: {f'{median_ev_ebitda:.1f}x' if median_ev_ebitda else 'N/A'}")
        lines.append(f"Peer Median P/E: {f'{median_pe:.1f}x' if median_pe else 'N/A'}")
        lines.append(f"Peer Median EV/Revenue: {f'{median_ev_revenue:.1f}x' if median_ev_revenue else 'N/A'}")
        lines.append(f"Peer Median P/S: {f'{median_ps:.1f}x' if median_ps else 'N/A'}")
        if implied_ev_from_ebitda:
            lines.append(f"Comps-Implied EV (EV/EBITDA method): ${implied_ev_from_ebitda / 1e9:.1f}B")
        if implied_ev_from_revenue:
            lines.append(f"Comps-Implied EV (EV/Revenue method): ${implied_ev_from_revenue / 1e9:.1f}B")
        for p in (peers or [])[:5]:
            lines.append(
                f"  {p.get('ticker', '?')}: EV/EBITDA={p.get('ev_ebitda', 'N/A')}, "
                f"P/E={p.get('pe_ratio', 'N/A')}, EV/Rev={p.get('ev_revenue', 'N/A')}"
            )

    return "\n".join(lines)


# ── Agent entry point ─────────────────────────────────────────────────────────

def run_xavi(
    snapshot: str,
    news_context: str | None = None,
    user_question: str | None = None,
) -> str:
    """
    Run the Xavi agent with a pre-built fundamental snapshot.

    snapshot:      Output of build_fundamental_snapshot() — Cardinal's frozen data
    news_context:  Optional Tavily headlines (context only, cannot override data)
    user_question: Optional follow-up question from the user
    """
    parts = [f"[CARDINAL DATA]\n{snapshot}"]

    if news_context:
        parts.append(
            f"[NEWS CONTEXT — for background only, cannot override Cardinal data]\n{news_context}"
        )

    if user_question:
        parts.append(f"[USER QUESTION]\n{user_question}")
    else:
        parts.append(
            "[TASK]\nProvide your full structured fundamental analysis of this company "
            "using only the Cardinal data above."
        )

    prompt = "\n\n".join(parts)
    return generate(prompt, system_prompt=XAVI_SYSTEM_PROMPT, max_output_tokens=512)