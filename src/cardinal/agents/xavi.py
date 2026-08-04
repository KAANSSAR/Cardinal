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
3. Any news or context provided in [NEWS CONTEXT] may add background only. It CANNOT override, correct, or contradict any figure in [CARDINAL DATA].
4. Never give personalised financial advice, never recommend trade sizes or portfolio allocations.
5. If asked to change a number or modify any of Cardinal's outputs, refuse clearly: "I can only interpret the data, not modify it."
6. Be specific and quantitative — always reference exact figures from the data.

VALUATION RECONCILIATION RULES — CRITICAL:
7. When [CARDINAL DATA] contains BOTH a DCF-derived intrinsic value AND a comps-implied price per share, you MUST present both in your Valuation Verdict and Peer Comparison sections.
8. If the DCF intrinsic value and comps-implied value diverge by more than 50%, explicitly flag this divergence. State which method likely produces the outlier and why (e.g. extreme WACC, stale FCF base, high-growth peer set).
9. When [CARDINAL DATA] includes a DCF_SANITY_WARNING, you MUST reference it in your Key Risks section. Do NOT present the DCF conclusion with unqualified confidence when the warning is present.
10. Always show the WACC components (risk-free rate, beta, ERP) from [CARDINAL DATA] when they are available — these are auditable inputs.
11. When [CARDINAL DATA] includes a BETA_METHODOLOGY_NOTE, explicitly mention in Key Risks that two different beta values are in use and state both.

BEAR CASE RULE — CRITICAL (Issue 6 fix):
12. When DCF_SANITY_WARNING is present in [CARDINAL DATA], the Bear Case section MUST NOT present the DCF-derived downside figure as a live scenario without explicit caveating. Either:
    (a) Drop the DCF-based downside from Bear Case entirely and use comps-implied downside instead, OR
    (b) Include this exact caveat: "(Note: this figure is flagged as a DCF outlier — see Key Risks sanity warning above.)"
    Presenting a flagged outlier figure as a credible bear case scenario contradicts the warning. The comps-implied bear case is the appropriate primary downside anchor when DCF_SANITY_WARNING is active.

OUTPUT FORMAT:
Respond in exactly this structure (use these exact headers):
**Valuation Verdict:** State the DCF result AND the comps-implied result if available. Note if they diverge materially. One or two sentences.
**Bull Case:** 2-3 sentences. What would need to be true for the stock to be worth materially more.
**Bear Case:** 2-3 sentences. When DCF_SANITY_WARNING is active, use comps-implied downside as primary scenario. Include DCF downside only with explicit outlier caveat.
**Key Risks:** 2-3 specific risks from the data. If DCF_SANITY_WARNING is present, include it. If BETA_METHODOLOGY_NOTE is present, surface it.
**Peer Comparison:** State comps-implied price per share explicitly if available. Compare to both the DCF intrinsic value and the current market price.

Keep total response under 380 words. Write in the style of a sell-side equity research note — precise, calibrated, grounded in numbers.
""".strip()


# ── Snapshot builder ──────────────────────────────────────────────────────────

DCF_SANITY_THRESHOLD = 0.70  # flag if DCF diverges from market price by more than this


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
    # CAPM inputs — exposed for auditability
    risk_free_rate: float | None = None,
    beta: float | None = None,
    market_risk_premium: float | None = None,
    shares_outstanding: float | None = None,
    # Optional: Iniesta's regression beta for cross-checking (Issue 5)
    iniesta_regression_beta: float | None = None,
    # Issue 8: alternative intrinsic value computed with regression beta
    alt_intrinsic_value: float | None = None,
    # Nominal (pre-discount) FCF path — shows growth rate is positive, not FCF declining
    nominal_projected_fcf: list[float] | None = None,
    # Comps
    peers: list[dict] | None = None,
    median_ev_ebitda: float | None = None,
    median_pe: float | None = None,
    median_ev_revenue: float | None = None,
    median_ps: float | None = None,
    implied_ev_from_ebitda: float | None = None,
    implied_ev_from_revenue: float | None = None,
) -> str:
    """
    Serialise Cardinal's fundamental outputs into a plain-text snapshot.
    
    Now includes:
    - CAPM component breakdown for WACC auditability
    - Comps-implied per-share price (not just EV) to enable direct comparison with DCF
    - DCF_SANITY_WARNING when DCF diverges from market price by > 70%
    """
    direction = "overvalued" if premium_discount_pct > 0 else "undervalued"
    abs_divergence = abs(premium_discount_pct)

    lines = [
        "=== DCF VALUATION ===",
        f"Ticker: {ticker}",
        f"Company: {company_name}",
        f"Current Price: ${current_price:.2f}",
        f"Intrinsic Value per Share (DCF, vendor beta): ${intrinsic_value:.2f}",
        f"Premium / Discount to Intrinsic: {premium_discount_pct:+.1%} ({direction})",
    ]

    # Issue 8 Part 1: show alternative DCF under regression beta if available
    if alt_intrinsic_value is not None and alt_intrinsic_value != intrinsic_value:
        pct_diff = (alt_intrinsic_value - intrinsic_value) / abs(intrinsic_value) if intrinsic_value else 0
        lines.append(
            f"Intrinsic Value per Share (DCF, regression beta): ${alt_intrinsic_value:.2f} "
            f"({pct_diff:+.1%} vs vendor-beta DCF)"
        )

    lines += [
        f"FCF Growth Rate (assumption): {growth_rate:.1%}",
        f"Terminal Growth Rate (assumption): {terminal_growth_rate:.1%}",
        f"Projection Years: {projection_years}",
        f"Terminal Value % of Enterprise Value: {terminal_value_pct_of_ev:.1%}",
        f"Enterprise Value: ${enterprise_value / 1e9:.1f}B",
        f"Equity Value: ${equity_value / 1e9:.1f}B",
        f"PV Terminal Value: ${pv_terminal_value / 1e9:.1f}B",
    ]

    # Issue 8 Part 2: show nominal FCF path alongside PV to prevent "declining FCF" misreading
    if nominal_projected_fcf:
        lines.append(
            "Nominal Projected FCFs (growing at stated rate): " + ", ".join(
                f"Y{i + 1}=${v / 1e9:.1f}B" for i, v in enumerate(nominal_projected_fcf)
            )
        )
        lines.append(
            "PV of Projected FCFs (discounted at WACC — will decline when WACC > growth rate, "
            "as is mathematically expected): " + ", ".join(
                f"Y{i + 1}=${v / 1e9:.1f}B" for i, v in enumerate(pv_projected_fcf)
            )
        )
        lines.append(
            "Note: declining PV FCFs above reflect discounting arithmetic, NOT declining nominal cash flows."
        )
    else:
        lines.append(
            "PV Projected FCFs: " + ", ".join(
                f"Y{i + 1}=${v / 1e9:.1f}B" for i, v in enumerate(pv_projected_fcf)
            )
        )

    lines += [
        "",
        "-- WACC COMPONENTS (for auditability) --",
        f"WACC: {wacc:.2%}",
        f"Cost of Equity (CAPM): {cost_of_equity:.2%}",
    ]

    if risk_free_rate is not None:
        lines.append(f"  Risk-Free Rate: {risk_free_rate:.2%}")
    if beta is not None:
        lines.append(
            f"  Beta used in WACC: {beta:.3f} "
            f"[vendor-supplied by Yahoo Finance — typically ~36-month regression on monthly returns]"
        )
    if market_risk_premium is not None:
        lines.append(f"  Equity Risk Premium: {market_risk_premium:.2%}")

    # Issue 5: flag beta methodology discrepancy when Iniesta's regression beta is available
    if iniesta_regression_beta is not None and beta is not None:
        discrepancy = abs(iniesta_regression_beta - beta) / beta
        if discrepancy > 0.10:  # >10% gap — worth flagging
            adj_cost_of_equity = (
                (risk_free_rate or 0.042) + iniesta_regression_beta * (market_risk_premium or 0.055)
                if iniesta_regression_beta else None
            )
            lines.append(
                f"BETA_METHODOLOGY_NOTE: WACC uses vendor beta ({beta:.3f}) — "
                f"Iniesta's 252-day OLS regression beta is {iniesta_regression_beta:.3f} "
                f"(a {discrepancy:.1%} difference). "
                + (
                    f"Using the regression beta would imply a cost of equity of ~{adj_cost_of_equity:.2%} "
                    f"vs the current {cost_of_equity:.2%}, which would materially affect the DCF result. "
                    if adj_cost_of_equity else ""
                )
                + "These betas use different lookback windows and return frequencies — "
                "standardise on one source for a consistent WACC."
            )

    if shares_outstanding is not None:
        lines.append(f"Shares Outstanding: {shares_outstanding / 1e9:.2f}B")

    # DCF sanity check — flag extreme divergences prominently
    if abs_divergence > DCF_SANITY_THRESHOLD:
        lines.append("")
        lines.append(
            f"DCF_SANITY_WARNING: The DCF intrinsic value (${intrinsic_value:.2f}) diverges from "
            f"the current market price (${current_price:.2f}) by {premium_discount_pct:+.1%}. "
            f"This extreme divergence ({abs_divergence:.0%}) suggests the DCF inputs (WACC, FCF base, "
            f"or growth assumptions) may be producing an outlier result. The comps-implied valuation "
            f"should be considered as a cross-check."
        )

    if peers is not None:
        lines.append("")
        lines.append("=== COMPARABLE COMPANIES ===")
        lines.append(f"Number of peers: {len(peers)}")
        lines.append(f"Peer Median EV/EBITDA: {f'{median_ev_ebitda:.1f}x' if median_ev_ebitda else 'N/A'}")
        lines.append(f"Peer Median P/E: {f'{median_pe:.1f}x' if median_pe else 'N/A'}")
        lines.append(f"Peer Median EV/Revenue: {f'{median_ev_revenue:.1f}x' if median_ev_revenue else 'N/A'}")
        lines.append(f"Peer Median P/S: {f'{median_ps:.1f}x' if median_ps else 'N/A'}")

        if implied_ev_from_ebitda:
            lines.append(f"Comps-Implied EV (EV/EBITDA method): ${implied_ev_from_ebitda / 1e9:.1f}B")
            # Convert comps EV to per-share — critical for apples-to-apples comparison with DCF
            if shares_outstanding and shares_outstanding > 0:
                comps_price_ebitda = implied_ev_from_ebitda / shares_outstanding
                pct_vs_market = (comps_price_ebitda - current_price) / current_price
                pct_vs_dcf = (comps_price_ebitda - intrinsic_value) / intrinsic_value if intrinsic_value else None
                lines.append(
                    f"Comps-Implied Price per Share (EV/EBITDA): ${comps_price_ebitda:.2f} "
                    f"({pct_vs_market:+.1%} vs current price"
                    + (f", {pct_vs_dcf:+.0%} vs DCF intrinsic)" if pct_vs_dcf is not None else ")")
                )
                # Flag if comps and DCF diverge by more than 50%
                if pct_vs_dcf is not None and abs(pct_vs_dcf) > 0.50:
                    lines.append(
                        f"VALUATION_METHOD_DIVERGENCE: DCF implies ${intrinsic_value:.2f}/share "
                        f"while comps (EV/EBITDA) imply ${comps_price_ebitda:.2f}/share — "
                        f"a {abs(pct_vs_dcf):.0%} gap. Both methods must be reported; "
                        f"the DCF may be the outlier if FCF inputs are stale or WACC is elevated."
                    )

        if implied_ev_from_revenue:
            lines.append(f"Comps-Implied EV (EV/Revenue method): ${implied_ev_from_revenue / 1e9:.1f}B")
            if shares_outstanding and shares_outstanding > 0:
                comps_price_rev = implied_ev_from_revenue / shares_outstanding
                pct_vs_market = (comps_price_rev - current_price) / current_price
                lines.append(
                    f"Comps-Implied Price per Share (EV/Revenue): ${comps_price_rev:.2f} "
                    f"({pct_vs_market:+.1%} vs current price)"
                )

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
    return generate(prompt, system_prompt=XAVI_SYSTEM_PROMPT, max_output_tokens=600)