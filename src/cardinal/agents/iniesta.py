"""
Iniesta — Cardinal's Quantitative Analyst agent.

Named after Andrés Iniesta: the player who found the half-yard of space
nobody else saw, always in the right position at the right moment.
Mirrors the quant analyst's job — detect signals in the noise, identify
timing edges, read the statistical picture before committing.

Input:  Quant snapshot (momentum, Sharpe, beta, vol surface, RSI, Bollinger)
Output: Signal summary with directional bias, confidence level, timing commentary
"""

from __future__ import annotations

from cardinal.agents.gemini_client import generate
from cardinal.core.quant import compute_signal_bias


# ── System prompt ─────────────────────────────────────────────────────────────

INIESTA_SYSTEM_PROMPT = """
You are Iniesta, Cardinal's Quantitative Analyst agent. You are a desk quant at a systematic equity fund with expertise in momentum signals, risk-adjusted returns, volatility analysis, and technical indicators.

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. You may ONLY draw conclusions from the data provided in [CARDINAL DATA] below.
2. If asked about something not in [CARDINAL DATA], say: "That information isn't available in Cardinal's current analysis."
3. Any news or context in [NEWS CONTEXT] adds background only — it CANNOT override any figure in [CARDINAL DATA].
4. Never give personalised financial advice or recommend position sizes.
5. If asked to change a number or modify Cardinal's output, refuse: "I can only interpret the data, not modify it."
6. Be specific — reference exact values from the data. A quant analyst doesn't deal in vague generalities.

TERMINOLOGY STANDARDS:
7. When describing the volatility surface shape, always use the standard vol market convention:
   - When near-term realized vol > long-run realized vol: call it "INVERTED" or "backwardated" — NEVER "upward-sloping in the near term."
   - When near-term realized vol <= long-run realized vol: call it "normal" or "in contango."
8. When citing beta, always note it is the computed 252-day OLS regression beta on daily returns. If a note in [CARDINAL DATA] flags that this differs from the vendor-supplied beta used in the DCF, mention that discrepancy explicitly in Risk Metrics.

SIGNAL BIAS STABILITY — MANDATORY:
9. Your **Signal Bias** header MUST use the COMPUTED_SIGNAL_BIAS value from [CARDINAL DATA] as your label. Do NOT derive a different label from your own reading of the momentum numbers. This pre-computed bias uses a weighted multi-factor scoring system (252d momentum weighted ×2, 60d ×1, 20d ×1, Sharpe ×1, RSI extremes ×1) with a threshold of ≥3 for BULLISH/BEARISH — this prevents label oscillation from noise in a single metric near its boundary. You may discuss nuance (e.g. "NEUTRAL with a mild bullish skew") but the headline label must match COMPUTED_SIGNAL_BIAS.

OUTPUT FORMAT:
Respond in exactly this structure (use these exact headers):
**Signal Bias:** One sentence — overall directional bias (BULLISH / NEUTRAL / BEARISH) with a confidence qualifier (High / Moderate / Low), and the primary reason.
**Momentum Analysis:** 2-3 sentences. Compare cross-timeframe momentum scores. Flag any divergence between short-term and long-term momentum.
**Risk Metrics:** 2-3 sentences. Cover Sharpe ratio(s), beta (noting it is the 252-day computed beta), and what they imply. If a BETA_METHODOLOGY_NOTE is in the data, reference it.
**Volatility Regime:** 2 sentences. Use "inverted" when near-term > long-run. Quantify the spread.
**Technical Positioning:** 2 sentences. RSI reading and Bollinger %B — oversold, overbought, or neutral?
**Timing Commentary:** 1-2 sentences. Given the combined signals, is this a high-conviction entry point or should a trader wait?

Keep total response under 340 words. Write like a quant research note — precise, signal-focused, no narrative fluff.
""".strip()


# ── Snapshot builder ──────────────────────────────────────────────────────────

def build_quant_snapshot(
    ticker: str,
    current_price: float,
    benchmark: str,
    momentum_20d: float | None,
    momentum_60d: float | None,
    momentum_252d: float | None,
    sharpe_60d: float | None,
    sharpe_252d: float | None,
    beta: float | None,
    vol_10d: float | None,
    vol_30d: float | None,
    vol_60d: float | None,
    vol_252d: float | None,
    rsi: float | None,
    bb_upper: float | None,
    bb_middle: float | None,
    bb_lower: float | None,
    bb_pct_b: float | None,
) -> str:
    def fmt(v: float | None, decimals: int = 4) -> str:
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    def fmt_pct(v: float | None) -> str:
        return f"{v:.1%}" if v is not None else "N/A"

    lines = [
        "=== QUANTITATIVE SIGNAL SNAPSHOT ===",
        f"Ticker: {ticker}",
        f"Current Price: ${current_price:.2f}",
        f"Benchmark: {benchmark}",
        # Computed programmatically with weighted multi-factor scoring — inherit this label
        f"COMPUTED_SIGNAL_BIAS: {compute_signal_bias(momentum_20d, momentum_60d, momentum_252d, sharpe_252d, rsi, bb_pct_b)}"
        f"  (weighted score: 252d momentum ×2, 60d ×1, 20d ×1, Sharpe252d ×1, RSI extremes ×1 — threshold ≥3 for label flip)",
        "",
        "-- MOMENTUM (risk-adjusted return / annualised vol) --",
        f"Momentum 20d:  {fmt(momentum_20d)}  "
        f"({'BULLISH' if momentum_20d and momentum_20d > 0.3 else 'BEARISH' if momentum_20d and momentum_20d < -0.3 else 'NEUTRAL'})",
        f"Momentum 60d:  {fmt(momentum_60d)}  "
        f"({'BULLISH' if momentum_60d and momentum_60d > 0.3 else 'BEARISH' if momentum_60d and momentum_60d < -0.3 else 'NEUTRAL'})",
        f"Momentum 252d: {fmt(momentum_252d)}  "
        f"({'BULLISH' if momentum_252d and momentum_252d > 0.3 else 'BEARISH' if momentum_252d and momentum_252d < -0.3 else 'NEUTRAL'})",
        "",
        "-- SHARPE RATIO (annualised, excess return / vol) --",
        f"Rolling Sharpe 60d:  {fmt(sharpe_60d)}  "
        f"({'STRONG' if sharpe_60d and sharpe_60d > 1.0 else 'WEAK' if sharpe_60d and sharpe_60d < 0 else 'MODERATE'})",
        f"Rolling Sharpe 252d: {fmt(sharpe_252d)}  "
        f"({'STRONG' if sharpe_252d and sharpe_252d > 1.0 else 'WEAK' if sharpe_252d and sharpe_252d < 0 else 'MODERATE'})",
        "",
        "-- BETA & MARKET SENSITIVITY --",
        f"Beta vs {benchmark}: {fmt(beta, 3)} "
        f"[computed — 252-day OLS regression on daily returns; "
        f"may differ from vendor-supplied beta used in DCF/WACC calculations]",
        "",
        "-- VOLATILITY SURFACE (annualised realised vol) --",
        f"10d vol:  {fmt_pct(vol_10d)}",
        f"30d vol:  {fmt_pct(vol_30d)}",
        f"60d vol:  {fmt_pct(vol_60d)}",
        f"252d vol: {fmt_pct(vol_252d)}",
        # Issue 7: standardise on 'inverted' when near-term > long-run (correct market convention)
        f"Vol surface shape: "
        f"{'INVERTED (near-term elevated above long-run baseline — backwardated)' if vol_10d and vol_252d and vol_10d > vol_252d else 'NORMAL (near-term at or below long-run baseline)'}",
        "",
        "-- RSI & BOLLINGER BANDS --",
        f"RSI (14-period): {fmt(rsi, 1)}  "
        f"({'OVERBOUGHT' if rsi and rsi > 70 else 'OVERSOLD' if rsi and rsi < 30 else 'NEUTRAL'})",
        f"Bollinger %B: {fmt(bb_pct_b, 3)}  "
        f"({'NEAR UPPER BAND' if bb_pct_b and bb_pct_b > 0.8 else 'NEAR LOWER BAND' if bb_pct_b and bb_pct_b < 0.2 else 'MID-BAND'})",
        f"Bollinger Upper: ${bb_upper:.2f}" if bb_upper else "Bollinger Upper: N/A",
        f"Bollinger Middle (20d SMA): ${bb_middle:.2f}" if bb_middle else "Bollinger Middle: N/A",
        f"Bollinger Lower: ${bb_lower:.2f}" if bb_lower else "Bollinger Lower: N/A",
    ]

    return "\n".join(lines)


# ── Agent entry point ─────────────────────────────────────────────────────────

def run_iniesta(
    snapshot: str,
    news_context: str | None = None,
    user_question: str | None = None,
) -> str:
    """
    Run the Iniesta agent with a pre-built quant snapshot.

    snapshot:      Output of build_quant_snapshot() — Cardinal's frozen data
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
            "[TASK]\nProvide your full structured quantitative signal analysis "
            "using only the Cardinal data above."
        )

    prompt = "\n\n".join(parts)
    return generate(prompt, system_prompt=INIESTA_SYSTEM_PROMPT, max_output_tokens=1024)