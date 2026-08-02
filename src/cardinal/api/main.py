"""Cardinal FastAPI application."""
from __future__ import annotations

import httpx
import yfinance as yf

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from cardinal.api.models import (
    AgentRequest, AgentResponse, BusquetsRequest, MessiRequest, MessiResponse,
    BacktestResponse, BalanceSheetResponse, CompsResponse, CurvePoint,
    DCFAssumptionsRequest, DCFResponse, IncomeStatementResponse,
    PeerMetricsOut, PriceHistoryResponse, PricePoint,
    QuantResponse, SearchResponse, SearchResult,
)
from cardinal.agents.gemini_client import GeminiNotConfiguredError
from cardinal.agents.xavi import build_fundamental_snapshot, run_xavi
from cardinal.agents.iniesta import build_quant_snapshot, run_iniesta
from cardinal.agents.busquets import build_backtest_snapshot, run_busquets
from cardinal.agents.messi import run_messi
from cardinal.agents import cache as agent_cache
from cardinal.config import settings
from cardinal.core.backtest import run_mean_reversion_backtest, run_momentum_backtest
from cardinal.core.comps import PeerMetrics, compute_comps
from cardinal.core.dcf import DCFAssumptions, run_dcf
from cardinal.core.quant import benchmark_for_ticker, compute_quant_snapshot
from cardinal.data.fmp_client import (
    FMPNotConfiguredError, FMPRequestError,
    TickerNotFoundError as FMPTickerNotFoundError,
    get_balance_sheet_statement, get_income_statement,
    get_profile, get_stock_peers,
)
from cardinal.data.market_data import (
    InsufficientDataError, TickerNotFoundError,
    fetch_company_profile, fetch_financial_snapshot, fetch_price_history,
)

app = FastAPI(
    title="Cardinal API",
    description="Multi-lens equity analysis terminal.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search_tickers(q: str = Query(..., min_length=1)) -> SearchResponse:
    try:
        response = httpx.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": False},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5.0,
        )
        data = response.json()
        quotes = data.get("quotes", [])
        results = [
            SearchResult(
                symbol=quote["symbol"],
                name=quote.get("longname") or quote.get("shortname") or quote["symbol"],
                exchange=quote.get("exchange"),
                type=quote.get("quoteType"),
            )
            for quote in quotes
            if quote.get("symbol") and quote.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")
        ]
        return SearchResponse(query=q, results=results[:8])
    except Exception:
        return SearchResponse(query=q, results=[])


@app.get("/ticker/{symbol}/dcf", response_model=DCFResponse)
def get_dcf(
    symbol: str,
    growth_rate: float = 0.08,
    terminal_growth_rate: float = 0.035,
    projection_years: int = 5,
    wacc_override: float | None = None,
) -> DCFResponse:
    try:
        snapshot = fetch_financial_snapshot(symbol)
        profile = fetch_company_profile(symbol)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        request = DCFAssumptionsRequest(
            growth_rate=growth_rate,
            terminal_growth_rate=terminal_growth_rate,
            projection_years=projection_years,
            wacc_override=wacc_override,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        assumptions = DCFAssumptions(
            growth_rate=request.growth_rate,
            terminal_growth_rate=request.terminal_growth_rate,
            projection_years=request.projection_years,
            wacc_override=request.wacc_override,
        )
        result = run_dcf(snapshot, assumptions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DCFResponse(
        ticker=snapshot.ticker, company_name=profile.name,
        wacc=result.wacc, cost_of_equity=result.cost_of_equity,
        projected_fcf=result.projected_fcf, pv_projected_fcf=result.pv_projected_fcf,
        pv_terminal_value=result.pv_terminal_value,
        terminal_value_pct_of_ev=result.terminal_value_pct_of_ev,
        enterprise_value=result.enterprise_value, equity_value=result.equity_value,
        intrinsic_value_per_share=result.intrinsic_value_per_share,
        current_price=result.current_price, premium_discount_pct=result.premium_discount_pct,
    )


@app.get("/ticker/{symbol}/price-history", response_model=PriceHistoryResponse)
def get_price_history(symbol: str, period: str = "5y", interval: str = "1d") -> PriceHistoryResponse:
    try:
        history = fetch_price_history(symbol, period=period, interval=interval)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    points = [
        PricePoint(
            date=str(index.date()), open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]), volume=int(row["Volume"]),
        )
        for index, row in history.iterrows()
    ]
    return PriceHistoryResponse(ticker=symbol.upper(), period=period, interval=interval, points=points)


@app.get("/ticker/{symbol}/income-statement", response_model=IncomeStatementResponse)
def get_income_statement_endpoint(symbol: str, limit: int = 3) -> IncomeStatementResponse:
    try:
        statements = get_income_statement(symbol, limit=limit)
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except FMPTickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FMPRequestError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return IncomeStatementResponse(ticker=symbol.upper(), statements=statements)


@app.get("/ticker/{symbol}/balance-sheet", response_model=BalanceSheetResponse)
def get_balance_sheet_endpoint(symbol: str, limit: int = 3) -> BalanceSheetResponse:
    try:
        statements = get_balance_sheet_statement(symbol, limit=limit)
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except FMPTickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FMPRequestError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return BalanceSheetResponse(ticker=symbol.upper(), statements=statements)


def _build_peer_metrics_yf(ticker: str) -> PeerMetrics | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or (not info.get("regularMarketPrice") and not info.get("currentPrice")):
            return None
        market_cap = info.get("marketCap")
        name = info.get("longName") or info.get("shortName") or ticker
        revenue = info.get("totalRevenue")
        net_income = info.get("netIncomeToCommon")
        ebitda = info.get("ebitda")
        total_debt = info.get("totalDebt") or 0
        cash = info.get("totalCash") or 0
        ev_raw = (market_cap or 0) + total_debt - cash
        ev = ev_raw if ev_raw > 0 else None
        pe = info.get("trailingPE")
        ps = info.get("priceToSalesTrailing12Months")
        ev_ebitda = info.get("enterpriseToEbitda")
        ev_revenue = info.get("enterpriseToRevenue")
        if pe is None and market_cap and net_income and net_income > 0:
            pe = market_cap / net_income
        if ps is None and market_cap and revenue and revenue > 0:
            ps = market_cap / revenue
        if ev_ebitda is None and ev and ebitda and ebitda > 0:
            ev_ebitda = ev / ebitda
        if ev_revenue is None and ev and revenue and revenue > 0:
            ev_revenue = ev / revenue
        return PeerMetrics(
            ticker=ticker.upper(), name=name, market_cap=market_cap, enterprise_value=ev,
            ev_ebitda=ev_ebitda, pe_ratio=pe, ev_revenue=ev_revenue, ps_ratio=ps,
            revenue_ttm=revenue, ebitda_ttm=ebitda,
        )
    except Exception:
        return None


@app.get("/ticker/{symbol}/comps", response_model=CompsResponse)
def get_comps(symbol: str) -> CompsResponse:
    def _require_fmp() -> None:
        if not settings.fmp_configured:
            raise FMPNotConfiguredError("FMP_API_KEY is not set.")

    try:
        _require_fmp()
        peer_tickers = get_stock_peers(symbol)[:5]
        target_metrics = _build_peer_metrics_yf(symbol)
        if target_metrics is None:
            raise FMPRequestError(f"Could not fetch metrics for '{symbol}'")
        peers_built = [pm for t in peer_tickers if (pm := _build_peer_metrics_yf(t)) is not None]
        result = compute_comps(symbol.upper(), target_metrics, peers_built)
        peers_out = [
            PeerMetricsOut(
                ticker=p.ticker, name=p.name, market_cap=p.market_cap,
                enterprise_value=p.enterprise_value, ev_ebitda=p.ev_ebitda,
                pe_ratio=p.pe_ratio, ev_revenue=p.ev_revenue, ps_ratio=p.ps_ratio,
            )
            for p in result.peers
        ]
        return CompsResponse(
            ticker=symbol.upper(), peers=peers_out,
            median_ev_ebitda=result.median_ev_ebitda, median_pe=result.median_pe,
            median_ev_revenue=result.median_ev_revenue, median_ps=result.median_ps,
            implied_ev_from_ebitda=result.implied_ev_from_ebitda,
            implied_ev_from_revenue=result.implied_ev_from_revenue,
        )
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except (FMPRequestError, FMPTickerNotFoundError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/ticker/{symbol}/quant", response_model=QuantResponse)
def get_quant(symbol: str) -> QuantResponse:
    """
    Quantitative analytics overlay.
    Fetches 5y price history for the ticker and its benchmark,
    then computes momentum, Sharpe, beta, volatility surface, RSI, and Bollinger bands.
    """
    try:
        history = fetch_price_history(symbol, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{symbol}'")

    prices = history["Close"].dropna()
    benchmark_sym = benchmark_for_ticker(symbol)

    # Fetch benchmark — don't fail the whole request if it's unavailable
    bench_prices = None
    try:
        bench_hist = fetch_price_history(benchmark_sym, period="5y", interval="1d")
        if not bench_hist.empty:
            bench_prices = bench_hist["Close"].dropna()
    except Exception:
        pass

    try:
        snap = compute_quant_snapshot(symbol.upper(), prices, bench_prices)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quant computation failed: {e}") from e

    return QuantResponse(
        ticker=snap.ticker,
        current_price=snap.current_price,
        benchmark=benchmark_sym,
        momentum_20d=snap.momentum_20d,
        momentum_60d=snap.momentum_60d,
        momentum_252d=snap.momentum_252d,
        sharpe_60d=snap.sharpe_60d,
        sharpe_252d=snap.sharpe_252d,
        beta=snap.beta,
        vol_10d=snap.vol_10d,
        vol_30d=snap.vol_30d,
        vol_60d=snap.vol_60d,
        vol_252d=snap.vol_252d,
        rsi=snap.rsi,
        bb_upper=snap.bb_upper,
        bb_middle=snap.bb_middle,
        bb_lower=snap.bb_lower,
        bb_pct_b=snap.bb_pct_b,
    )


@app.get("/ticker/{symbol}/backtest", response_model=BacktestResponse)
def get_backtest(
    symbol: str,
    strategy: str = "momentum",
    fast_window: int = 50,
    slow_window: int = 200,
    lookback: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    commission: float = 0.001,
) -> BacktestResponse:
    """
    Algo backtest endpoint.
    strategy: 'momentum' (Golden/Death Cross) or 'mean_reversion' (z-score)
    """
    try:
        history = fetch_price_history(symbol, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{symbol}'")

    prices = history["Close"].dropna()

    try:
        if strategy == "momentum":
            result = run_momentum_backtest(
                symbol.upper(), prices,
                fast_window=fast_window, slow_window=slow_window, commission=commission,
            )
        elif strategy == "mean_reversion":
            result = run_mean_reversion_backtest(
                symbol.upper(), prices,
                lookback=lookback, entry_z=entry_z, exit_z=exit_z, commission=commission,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown strategy '{strategy}'. Use 'momentum' or 'mean_reversion'.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return BacktestResponse(
        ticker=result.ticker,
        strategy=result.strategy,
        params=result.params,
        total_return=result.total_return,
        buy_hold_return=result.buy_hold_return,
        sharpe=result.sharpe,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        num_trades=result.num_trades,
        avg_win=result.avg_win,
        avg_loss=result.avg_loss,
        pnl_curve=[CurvePoint(date=p["date"], value=p["value"]) for p in result.pnl_curve],
        buy_hold_curve=[CurvePoint(date=p["date"], value=p["value"]) for p in result.buy_hold_curve],
    )

@app.post("/agent/xavi", response_model=AgentResponse)
def post_xavi(request: AgentRequest) -> AgentResponse:
    """
    Xavi — Fundamental Analyst agent.
    Fetches Cardinal's DCF + comps data for the ticker, builds a frozen
    read-only snapshot, and passes it to Gemini 2.5 Flash with strict
    guardrails. The agent cannot modify any data — it only interprets it.
    """
    # 1. Fetch DCF data (re-uses existing endpoint logic)
    try:
        snapshot_data = fetch_financial_snapshot(request.ticker)
        profile = fetch_company_profile(request.ticker)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        assumptions = DCFAssumptions(
            growth_rate=request.growth_rate,
            terminal_growth_rate=request.terminal_growth_rate,
            projection_years=request.projection_years,
            wacc_override=request.wacc_override,
        )
        dcf_result = run_dcf(snapshot_data, assumptions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 2. Fetch comps (best-effort — don't fail if unavailable)
    peers_list: list[dict] = []
    median_ev_ebitda = median_pe = median_ev_revenue = median_ps = None
    implied_ev_ebitda = implied_ev_revenue = None

    if settings.fmp_configured:
        try:
            peer_tickers = get_stock_peers(request.ticker)[:5]
            target_m = _build_peer_metrics_yf(request.ticker)
            if target_m:
                peers_built = [
                    pm for t in peer_tickers
                    if (pm := _build_peer_metrics_yf(t)) is not None
                ]
                comps_result = compute_comps(request.ticker.upper(), target_m, peers_built)
                median_ev_ebitda = comps_result.median_ev_ebitda
                median_pe = comps_result.median_pe
                median_ev_revenue = comps_result.median_ev_revenue
                median_ps = comps_result.median_ps
                implied_ev_ebitda = comps_result.implied_ev_from_ebitda
                implied_ev_revenue = comps_result.implied_ev_from_revenue
                peers_list = [
                    {
                        "ticker": p.ticker,
                        "ev_ebitda": round(p.ev_ebitda, 2) if p.ev_ebitda else None,
                        "pe_ratio": round(p.pe_ratio, 2) if p.pe_ratio else None,
                        "ev_revenue": round(p.ev_revenue, 2) if p.ev_revenue else None,
                    }
                    for p in comps_result.peers
                ]
        except Exception:
            pass  # comps are best-effort; agent still runs without them

    # 3. Build frozen snapshot string
    snapshot_str = build_fundamental_snapshot(
        ticker=request.ticker.upper(),
        company_name=profile.name,
        current_price=dcf_result.current_price,
        intrinsic_value=dcf_result.intrinsic_value_per_share,
        premium_discount_pct=dcf_result.premium_discount_pct,
        wacc=dcf_result.wacc,
        cost_of_equity=dcf_result.cost_of_equity,
        growth_rate=request.growth_rate,
        terminal_growth_rate=request.terminal_growth_rate,
        projection_years=request.projection_years,
        terminal_value_pct_of_ev=dcf_result.terminal_value_pct_of_ev,
        enterprise_value=dcf_result.enterprise_value,
        equity_value=dcf_result.equity_value,
        pv_projected_fcf=dcf_result.pv_projected_fcf,
        pv_terminal_value=dcf_result.pv_terminal_value,
        peers=peers_list or None,
        median_ev_ebitda=median_ev_ebitda,
        median_pe=median_pe,
        median_ev_revenue=median_ev_revenue,
        median_ps=median_ps,
        implied_ev_from_ebitda=implied_ev_ebitda,
        implied_ev_from_revenue=implied_ev_revenue,
    )

    # 4. Call Gemini — check cache first
    xavi_key = agent_cache.make_key(
        "xavi", request.ticker.upper(),
        request.growth_rate, request.terminal_growth_rate,
        request.projection_years, request.wacc_override,
    )
    cached = agent_cache.get(xavi_key)
    if cached:
        return AgentResponse(agent="xavi", ticker=request.ticker.upper(), memo=cached, news_used=False)

    try:
        memo = run_xavi(
            snapshot=snapshot_str,
            user_question=request.user_question,
        )
    except GeminiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Xavi agent error: {e}") from e

    agent_cache.set(xavi_key, memo)
    return AgentResponse(agent="xavi", ticker=request.ticker.upper(), memo=memo, news_used=False)


@app.post("/agent/iniesta", response_model=AgentResponse)
def post_iniesta(request: AgentRequest) -> AgentResponse:
    """
    Iniesta — Quantitative Analyst agent.
    Fetches Cardinal's quant signal snapshot for the ticker and passes
    it to Gemini 3.5 Flash with strict read-only guardrails.
    """
    try:
        history = fetch_price_history(request.ticker, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{request.ticker}'")

    prices = history["Close"].dropna()
    benchmark_sym = benchmark_for_ticker(request.ticker)

    bench_prices = None
    try:
        bench_hist = fetch_price_history(benchmark_sym, period="5y", interval="1d")
        if not bench_hist.empty:
            bench_prices = bench_hist["Close"].dropna()
    except Exception:
        pass

    try:
        snap = compute_quant_snapshot(request.ticker.upper(), prices, bench_prices)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quant computation failed: {e}") from e

    snapshot_str = build_quant_snapshot(
        ticker=snap.ticker,
        current_price=snap.current_price,
        benchmark=benchmark_sym,
        momentum_20d=snap.momentum_20d,
        momentum_60d=snap.momentum_60d,
        momentum_252d=snap.momentum_252d,
        sharpe_60d=snap.sharpe_60d,
        sharpe_252d=snap.sharpe_252d,
        beta=snap.beta,
        vol_10d=snap.vol_10d,
        vol_30d=snap.vol_30d,
        vol_60d=snap.vol_60d,
        vol_252d=snap.vol_252d,
        rsi=snap.rsi,
        bb_upper=snap.bb_upper,
        bb_middle=snap.bb_middle,
        bb_lower=snap.bb_lower,
        bb_pct_b=snap.bb_pct_b,
    )

    # Iniesta cache key — depends only on ticker (no user-tunable params)
    iniesta_key = agent_cache.make_key("iniesta", request.ticker.upper())
    cached = agent_cache.get(iniesta_key)
    if cached:
        return AgentResponse(agent="iniesta", ticker=request.ticker.upper(), memo=cached, news_used=False)

    try:
        memo = run_iniesta(
            snapshot=snapshot_str,
            user_question=request.user_question,
        )
    except GeminiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Iniesta agent error: {e}") from e

    agent_cache.set(iniesta_key, memo)
    return AgentResponse(agent="iniesta", ticker=request.ticker.upper(), memo=memo, news_used=False)


@app.post("/agent/busquets", response_model=AgentResponse)
def post_busquets(request: BusquetsRequest) -> AgentResponse:
    """
    Busquets — Strategy Reviewer agent.
    Runs the selected backtest strategy on the ticker, builds a frozen
    read-only snapshot of the results, and passes it to Gemini with
    strict guardrails. The agent cannot modify any data.
    """
    try:
        history = fetch_price_history(request.ticker, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{request.ticker}'")

    prices = history["Close"].dropna()

    try:
        if request.strategy == "momentum":
            result = run_momentum_backtest(
                request.ticker.upper(), prices,
                fast_window=request.fast_window,
                slow_window=request.slow_window,
                commission=request.commission,
            )
        elif request.strategy == "mean_reversion":
            result = run_mean_reversion_backtest(
                request.ticker.upper(), prices,
                lookback=request.lookback,
                entry_z=request.entry_z,
                commission=request.commission,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy '{request.strategy}'. Use 'momentum' or 'mean_reversion'."
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    snapshot_str = build_backtest_snapshot(
        ticker=result.ticker,
        strategy=result.strategy,
        params=result.params,
        total_return=result.total_return,
        buy_hold_return=result.buy_hold_return,
        sharpe=result.sharpe,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        num_trades=result.num_trades,
        avg_win=result.avg_win,
        avg_loss=result.avg_loss,
        pnl_curve=result.pnl_curve,
        buy_hold_curve=result.buy_hold_curve,
    )

    # Busquets cache key — depends on ticker + strategy + params
    busquets_key = agent_cache.make_key(
        "busquets", request.ticker.upper(), request.strategy,
        request.fast_window, request.slow_window,
        request.lookback, request.entry_z, request.commission,
    )
    cached = agent_cache.get(busquets_key)
    if cached:
        return AgentResponse(agent="busquets", ticker=request.ticker.upper(), memo=cached, news_used=False)

    try:
        memo = run_busquets(
            snapshot=snapshot_str,
            user_question=request.user_question,
        )
    except GeminiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Busquets agent error: {e}") from e

    agent_cache.set(busquets_key, memo)
    return AgentResponse(agent="busquets", ticker=request.ticker.upper(), memo=memo, news_used=False)


@app.post("/agent/messi", response_model=MessiResponse)
def post_messi(request: MessiRequest) -> MessiResponse:
    """
    Messi — Portfolio Manager synthesis agent.
    Orchestrates the full team but checks each agent's cache first.
    Only re-runs agents whose cached memo has expired or doesn't exist.
    Returns all four memos so the frontend can populate each sidebar tab.
    """
    ticker = request.ticker.upper()
    cached_agents: list[str] = []

    # ── Cache keys ────────────────────────────────────────────────────────────
    xavi_key = agent_cache.make_key(
        "xavi", ticker,
        request.growth_rate, request.terminal_growth_rate,
        request.projection_years, request.wacc_override,
    )
    iniesta_key = agent_cache.make_key("iniesta", ticker)
    busquets_key = agent_cache.make_key(
        "busquets", ticker, request.strategy,
        request.fast_window, request.slow_window,
        request.lookback, request.entry_z, request.commission,
    )

    xavi_memo = agent_cache.get(xavi_key)
    iniesta_memo = agent_cache.get(iniesta_key)
    busquets_memo = agent_cache.get(busquets_key)

    if xavi_memo:
        cached_agents.append("xavi")
    if iniesta_memo:
        cached_agents.append("iniesta")
    if busquets_memo:
        cached_agents.append("busquets")

    # ── Step 1: Xavi (only if not cached) ────────────────────────────────────
    if not xavi_memo:
        try:
            snapshot_data = fetch_financial_snapshot(request.ticker)
            profile = fetch_company_profile(request.ticker)
        except TickerNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except InsufficientDataError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        try:
            dcf_assumptions = DCFAssumptions(
                growth_rate=request.growth_rate,
                terminal_growth_rate=request.terminal_growth_rate,
                projection_years=request.projection_years,
                wacc_override=request.wacc_override,
            )
            dcf_result = run_dcf(snapshot_data, dcf_assumptions)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        peers_list: list[dict] = []
        median_ev_ebitda = median_pe = median_ev_revenue = median_ps = None
        implied_ev_ebitda = implied_ev_revenue = None
        if settings.fmp_configured:
            try:
                peer_tickers = get_stock_peers(request.ticker)[:5]
                target_m = _build_peer_metrics_yf(request.ticker)
                if target_m:
                    peers_built = [
                        pm for t in peer_tickers
                        if (pm := _build_peer_metrics_yf(t)) is not None
                    ]
                    comps_result = compute_comps(ticker, target_m, peers_built)
                    median_ev_ebitda = comps_result.median_ev_ebitda
                    median_pe = comps_result.median_pe
                    median_ev_revenue = comps_result.median_ev_revenue
                    median_ps = comps_result.median_ps
                    implied_ev_ebitda = comps_result.implied_ev_from_ebitda
                    implied_ev_revenue = comps_result.implied_ev_from_revenue
                    peers_list = [
                        {
                            "ticker": p.ticker,
                            "ev_ebitda": round(p.ev_ebitda, 2) if p.ev_ebitda else None,
                            "pe_ratio": round(p.pe_ratio, 2) if p.pe_ratio else None,
                            "ev_revenue": round(p.ev_revenue, 2) if p.ev_revenue else None,
                        }
                        for p in comps_result.peers
                    ]
            except Exception:
                pass

        xavi_snapshot = build_fundamental_snapshot(
            ticker=ticker, company_name=profile.name,
            current_price=dcf_result.current_price,
            intrinsic_value=dcf_result.intrinsic_value_per_share,
            premium_discount_pct=dcf_result.premium_discount_pct,
            wacc=dcf_result.wacc, cost_of_equity=dcf_result.cost_of_equity,
            growth_rate=request.growth_rate,
            terminal_growth_rate=request.terminal_growth_rate,
            projection_years=request.projection_years,
            terminal_value_pct_of_ev=dcf_result.terminal_value_pct_of_ev,
            enterprise_value=dcf_result.enterprise_value,
            equity_value=dcf_result.equity_value,
            pv_projected_fcf=dcf_result.pv_projected_fcf,
            pv_terminal_value=dcf_result.pv_terminal_value,
            peers=peers_list or None,
            median_ev_ebitda=median_ev_ebitda, median_pe=median_pe,
            median_ev_revenue=median_ev_revenue, median_ps=median_ps,
            implied_ev_from_ebitda=implied_ev_ebitda,
            implied_ev_from_revenue=implied_ev_revenue,
        )
        try:
            xavi_memo = run_xavi(snapshot=xavi_snapshot)
            agent_cache.set(xavi_key, xavi_memo)
        except GeminiNotConfiguredError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Xavi agent error: {e}") from e

    # ── Step 2: Iniesta + Busquets (share price history fetch) ───────────────
    if not iniesta_memo or not busquets_memo:
        try:
            history = fetch_price_history(request.ticker, period="5y", interval="1d")
        except TickerNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        prices = history["Close"].dropna()

        if not iniesta_memo:
            benchmark_sym = benchmark_for_ticker(request.ticker)
            bench_prices = None
            try:
                bench_hist = fetch_price_history(benchmark_sym, period="5y", interval="1d")
                if not bench_hist.empty:
                    bench_prices = bench_hist["Close"].dropna()
            except Exception:
                pass
            quant_snap = compute_quant_snapshot(ticker, prices, bench_prices)
            iniesta_snapshot = build_quant_snapshot(
                ticker=quant_snap.ticker, current_price=quant_snap.current_price,
                benchmark=benchmark_for_ticker(request.ticker),
                momentum_20d=quant_snap.momentum_20d, momentum_60d=quant_snap.momentum_60d,
                momentum_252d=quant_snap.momentum_252d, sharpe_60d=quant_snap.sharpe_60d,
                sharpe_252d=quant_snap.sharpe_252d, beta=quant_snap.beta,
                vol_10d=quant_snap.vol_10d, vol_30d=quant_snap.vol_30d,
                vol_60d=quant_snap.vol_60d, vol_252d=quant_snap.vol_252d,
                rsi=quant_snap.rsi, bb_upper=quant_snap.bb_upper,
                bb_middle=quant_snap.bb_middle, bb_lower=quant_snap.bb_lower,
                bb_pct_b=quant_snap.bb_pct_b,
            )
            try:
                iniesta_memo = run_iniesta(snapshot=iniesta_snapshot)
                agent_cache.set(iniesta_key, iniesta_memo)
            except GeminiNotConfiguredError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Iniesta agent error: {e}") from e

        if not busquets_memo:
            try:
                if request.strategy == "momentum":
                    bt_result = run_momentum_backtest(
                        ticker, prices,
                        fast_window=request.fast_window,
                        slow_window=request.slow_window,
                        commission=request.commission,
                    )
                else:
                    bt_result = run_mean_reversion_backtest(
                        ticker, prices,
                        lookback=request.lookback,
                        entry_z=request.entry_z,
                        commission=request.commission,
                    )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

            busquets_snapshot = build_backtest_snapshot(
                ticker=bt_result.ticker, strategy=bt_result.strategy, params=bt_result.params,
                total_return=bt_result.total_return, buy_hold_return=bt_result.buy_hold_return,
                sharpe=bt_result.sharpe, max_drawdown=bt_result.max_drawdown,
                win_rate=bt_result.win_rate, num_trades=bt_result.num_trades,
                avg_win=bt_result.avg_win, avg_loss=bt_result.avg_loss,
                pnl_curve=bt_result.pnl_curve, buy_hold_curve=bt_result.buy_hold_curve,
            )
            try:
                busquets_memo = run_busquets(snapshot=busquets_snapshot)
                agent_cache.set(busquets_key, busquets_memo)
            except GeminiNotConfiguredError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Busquets agent error: {e}") from e

    # ── Step 3: Messi synthesises ─────────────────────────────────────────────
    try:
        synthesis = run_messi(
            ticker=ticker,
            xavi_memo=xavi_memo,
            iniesta_memo=iniesta_memo,
            busquets_memo=busquets_memo,
            user_question=request.user_question,
        )
    except GeminiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Messi agent error: {e}") from e

    return MessiResponse(
        ticker=ticker,
        xavi_memo=xavi_memo,
        iniesta_memo=iniesta_memo,
        busquets_memo=busquets_memo,
        synthesis_memo=synthesis,
        news_used=False,
        cached_agents=cached_agents,
    )