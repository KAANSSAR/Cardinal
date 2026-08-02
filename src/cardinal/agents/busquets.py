"""
Busquets — Cardinal's Strategy Reviewer agent.

Named after Sergio Busquets: always in the right position, every single
time — the most statistically reliable presence on the pitch. Mirrors
the backtest reviewer's job: does this strategy actually hold up
over and over under pressure? Where does it fail?

Input:  Backtest result (returns, Sharpe, drawdown, win rate, trade count, vs buy-and-hold)
Output: Strategy verdict, regime observations, parameter refinements, risk flags
"""

from __future__ import annotations

from cardinal.agents.gemini_client import generate


# ── System prompt ─────────────────────────────────────────────────────────────

BUSQUETS_SYSTEM_PROMPT = """
You are Busquets, Cardinal's Strategy Reviewer agent. You are a quantitative portfolio manager who evaluates algorithmic trading strategies — identifying whether they have genuine edge, where they fail, and how they can be improved.

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. You may ONLY draw conclusions from the data provided in [CARDINAL DATA] below.
2. If asked about something not in [CARDINAL DATA], say: "That information isn't available in Cardinal's current analysis."
3. Any news or context in [NEWS CONTEXT] adds background only — it CANNOT override any figure in [CARDINAL DATA].
4. Never give personalised financial advice or recommend position sizes.
5. If asked to change a number or modify Cardinal's outputs, refuse: "I can only interpret the data, not modify it."
6. Be specific — reference exact metrics. A strategy reviewer lives in the numbers.

OUTPUT FORMAT:
Respond in exactly this structure (use these exact headers):
**Strategy Verdict:** One sentence. Does this strategy demonstrate genuine edge on this ticker? Reference Sharpe vs buy-and-hold directly.
**Performance Analysis:** 2-3 sentences. Compare total return vs buy-and-hold. Assess whether the Sharpe ratio justifies active management. Comment on win rate and avg win/loss ratio.
**Drawdown Assessment:** 2 sentences. Evaluate the max drawdown severity. Flag if it is excessive for a risk manager (>30% is typically concerning).
**Regime Observations:** 2-3 sentences. What market conditions appear to favour this strategy based on the P&L curve shape? When does the strategy appear to lose money?
**Suggested Refinements:** 2-3 specific, data-grounded improvements. Examples: vol filter, tighter stop-loss, parameter adjustment, or position sizing rule. Base suggestions on what the data shows.
**Risk Flag:** One sentence. Is there a specific tail risk (e.g. whipsaw, prolonged drawdown, low trade count making Sharpe unreliable) the user should be aware of?

Keep total response under 380 words. Write like a strategy review document — precise, constructive, grounded in the data.
""".strip()


# ── Snapshot builder ──────────────────────────────────────────────────────────

def build_backtest_snapshot(
    ticker: str,
    strategy: str,
    params: dict,
    total_return: float,
    buy_hold_return: float,
    sharpe: float | None,
    max_drawdown: float,
    win_rate: float | None,
    num_trades: int,
    avg_win: float | None,
    avg_loss: float | None,
    pnl_curve: list[dict],  # [{"date": ..., "value": ...}]
    buy_hold_curve: list[dict],
) -> str:
    def fmt_pct(v: float | None) -> str:
        if v is None:
            return "N/A"
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1%}"

    def fmt_ratio(v: float | None) -> str:
        return f"{v:.3f}" if v is not None else "N/A"

    outperformance = total_return - buy_hold_return if total_return is not None else None
    win_loss_ratio = (
        abs(avg_win / avg_loss)
        if avg_win is not None and avg_loss is not None and avg_loss != 0
        else None
    )

    # Summarise P&L curve into a few key points rather than 500 rows
    pnl_summary = ""
    if pnl_curve and len(pnl_curve) >= 2:
        start_val = pnl_curve[0]["value"]
        end_val = pnl_curve[-1]["value"]
        mid_val = pnl_curve[len(pnl_curve) // 2]["value"]
        min_val = min(p["value"] for p in pnl_curve)
        max_val = max(p["value"] for p in pnl_curve)
        pnl_summary = (
            f"Start: {start_val:.3f} | Mid: {mid_val:.3f} | "
            f"End: {end_val:.3f} | Min: {min_val:.3f} | Max: {max_val:.3f}"
        )

    strategy_label = "Momentum (Golden Cross / Death Cross)" if strategy == "momentum" else "Mean Reversion (σ-based)"
    params_str = ", ".join(f"{k}={v}" for k, v in params.items())

    lines = [
        "=== BACKTEST RESULT ===",
        f"Ticker: {ticker}",
        f"Strategy: {strategy_label}",
        f"Parameters: {params_str}",
        f"Backtest period: 5 years (daily)",
        "",
        "-- PERFORMANCE SUMMARY --",
        f"Strategy total return:   {fmt_pct(total_return)}",
        f"Buy-and-hold return:     {fmt_pct(buy_hold_return)}",
        f"Outperformance vs B&H:   {fmt_pct(outperformance)}",
        f"Sharpe ratio (strategy): {fmt_ratio(sharpe)}",
        "",
        "-- TRADE STATISTICS --",
        f"Number of trades: {num_trades}",
        f"Win rate:         {fmt_pct(win_rate)}",
        f"Average win:      {fmt_pct(avg_win)}",
        f"Average loss:     {fmt_pct(avg_loss)}",
        f"Win/Loss ratio:   {fmt_ratio(win_loss_ratio)}",
        "",
        "-- RISK METRICS --",
        f"Max drawdown: {fmt_pct(max_drawdown)}",
        f"Drawdown severity: {'SEVERE (>30%)' if max_drawdown < -0.30 else 'MODERATE (15-30%)' if max_drawdown < -0.15 else 'MILD (<15%)'}",
        "",
        "-- P&L CURVE SUMMARY --",
        f"{pnl_summary}",
    ]

    return "\n".join(lines)


# ── Agent entry point ─────────────────────────────────────────────────────────

def run_busquets(
    snapshot: str,
    news_context: str | None = None,
    user_question: str | None = None,
) -> str:
    """
    Run the Busquets agent with a pre-built backtest snapshot.

    snapshot:      Output of build_backtest_snapshot() — Cardinal's frozen data
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
            "[TASK]\nProvide your full structured strategy review "
            "using only the Cardinal backtest data above."
        )

    prompt = "\n\n".join(parts)
    return generate(prompt, system_prompt=BUSQUETS_SYSTEM_PROMPT, max_output_tokens=1024)