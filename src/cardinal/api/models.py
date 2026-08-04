from __future__ import annotations
from pydantic import BaseModel, Field


class DCFAssumptionsRequest(BaseModel):
    growth_rate: float = Field(default=0.08, ge=-0.5, le=1.0)
    terminal_growth_rate: float = Field(default=0.035, ge=0.0, le=0.10)
    projection_years: int = Field(default=5, ge=1, le=15)
    wacc_override: float | None = Field(default=None, ge=0.0, le=0.5)


class DCFResponse(BaseModel):
    ticker: str
    company_name: str
    exchange: str | None = None
    currency: str = "USD"
    usd_conversion_rate: float | None = None   # 1 {currency} = X USD
    current_price_usd: float | None = None     # price converted to USD

    # DCF outputs — None when partial (insufficient data)
    wacc: float | None = None
    cost_of_equity: float | None = None
    projected_fcf: list[float] = []
    pv_projected_fcf: list[float] = []
    pv_terminal_value: float | None = None
    terminal_value_pct_of_ev: float | None = None
    enterprise_value: float | None = None
    equity_value: float | None = None
    intrinsic_value_per_share: float | None = None
    current_price: float = 0.0
    premium_discount_pct: float | None = None

    # Partial response flag
    is_partial: bool = False
    partial_reason: str | None = None


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    points: list[PricePoint]


class IncomeStatementResponse(BaseModel):
    ticker: str
    statements: list[dict]


class BalanceSheetResponse(BaseModel):
    ticker: str
    statements: list[dict]


class PeerMetricsOut(BaseModel):
    ticker: str
    name: str
    market_cap: float | None
    enterprise_value: float | None
    ev_ebitda: float | None
    pe_ratio: float | None
    ev_revenue: float | None
    ps_ratio: float | None


class CompsResponse(BaseModel):
    ticker: str
    peers: list[PeerMetricsOut]
    median_ev_ebitda: float | None
    median_pe: float | None
    median_ev_revenue: float | None
    median_ps: float | None
    implied_ev_from_ebitda: float | None
    implied_ev_from_revenue: float | None


class SearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str | None
    type: str | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class QuantResponse(BaseModel):
    ticker: str
    current_price: float
    benchmark: str

    # Momentum
    momentum_20d: float | None
    momentum_60d: float | None
    momentum_252d: float | None

    # Sharpe
    sharpe_60d: float | None
    sharpe_252d: float | None

    # Beta
    beta: float | None

    # Volatility surface
    vol_10d: float | None
    vol_30d: float | None
    vol_60d: float | None
    vol_252d: float | None

    # RSI & Bollinger
    rsi: float | None
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    bb_pct_b: float | None


class CurvePoint(BaseModel):
    date: str
    value: float


class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    params: dict

    total_return: float
    buy_hold_return: float
    sharpe: float | None
    max_drawdown: float
    win_rate: float | None
    num_trades: int
    avg_win: float | None
    avg_loss: float | None

    pnl_curve: list[CurvePoint]
    buy_hold_curve: list[CurvePoint]


class MessiChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class MessiChatRequest(BaseModel):
    ticker: str
    xavi_memo: str
    iniesta_memo: str
    busquets_memo: str
    synthesis_memo: str
    message: str
    history: list[MessiChatMessage] = []


class MessiChatResponse(BaseModel):
    reply: str
    news_used: bool


class AgentRequest(BaseModel):
    ticker: str
    user_question: str | None = None
    # Optional: DCF assumption overrides from frontend sliders
    growth_rate: float = 0.08
    terminal_growth_rate: float = 0.035
    projection_years: int = 5
    wacc_override: float | None = None


class BusquetsRequest(BaseModel):
    ticker: str
    user_question: str | None = None
    strategy: str = "momentum"          # "momentum" or "mean_reversion"
    fast_window: int = 50               # momentum strategy
    slow_window: int = 200              # momentum strategy
    lookback: int = 20                  # mean reversion strategy
    entry_z: float = 2.0               # mean reversion strategy
    commission: float = 0.001


class MessiRequest(BaseModel):
    ticker: str
    user_question: str | None = None
    # DCF assumptions forwarded to Xavi
    growth_rate: float = 0.08
    terminal_growth_rate: float = 0.035
    projection_years: int = 5
    wacc_override: float | None = None
    # Backtest params forwarded to Busquets
    strategy: str = "momentum"
    fast_window: int = 50
    slow_window: int = 200
    lookback: int = 20
    entry_z: float = 2.0
    commission: float = 0.001


class MessiResponse(BaseModel):
    ticker: str
    xavi_memo: str
    iniesta_memo: str
    busquets_memo: str
    synthesis_memo: str   # Messi's final verdict
    news_used: bool
    cached_agents: list[str]  # which agents were served from cache e.g. ["iniesta"]
    response_time_ms: int = 0
    synthesis_params_hash: str = ""
    synthesis_approval_count: int = 0
    synthesis_rejection_count: int = 0
    synthesis_is_verified: bool = False


class AgentResponse(BaseModel):
    agent: str          # "xavi" | "iniesta" | "busquets" | "messi"
    ticker: str
    memo: str           # the agent's full text output
    news_used: bool     # whether Tavily news context was included
    response_time_ms: int = 0
    params_hash: str = ""           # for frontend feedback submission
    thought_process: str | None = None  # data snapshot sent to agent
    approval_count: int = 0
    rejection_count: int = 0
    is_verified: bool = False


class ErrorResponse(BaseModel):
    detail: str

class FeedbackRequest(BaseModel):
    ticker: str
    agent: str
    params_hash: str
    vote: str           # "positive" or "negative"
    comment: str | None = None


class FeedbackResponse(BaseModel):
    approval_count: int
    rejection_count: int
    is_verified: bool
    threshold: int
    message: str


class GTEntry(BaseModel):
    id: int
    ticker: str
    agent: str
    params_hash: str
    verdict: str | None
    approval_count: int
    rejection_count: int
    is_verified: bool
    response_time_ms: int | None
    created_at: str
    updated_at: str


class AdminMetricsResponse(BaseModel):
    total_calls: int
    gt_entries: int
    verified: int
    total_feedback: int
    positive: int
    approval_rate: float
    gemini_calls: int
    cache_hits: int
    gt_hits: int
    agent_stats: list[dict]
    recent_calls: list[dict]
    recent_feedback: list[dict]
    approval_threshold: int


# ── Market overview (homepage widgets) ──────────────────────────────────────

class MarketSparklinePoint(BaseModel):
    date: str
    value: float


class IndexQuoteOut(BaseModel):
    symbol: str
    name: str
    value: float
    change: float
    change_pct: float
    sparkline: list[MarketSparklinePoint]


class MarketIndicesResponse(BaseModel):
    indices: list[IndexQuoteOut]


class MoverQuoteOut(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float
    sparkline: list[MarketSparklinePoint]


class MarketMoversResponse(BaseModel):
    gainers: list[MoverQuoteOut]
    losers: list[MoverQuoteOut]


class SectorPerformanceOut(BaseModel):
    name: str
    etf_proxy: str
    change_pct: float


class SectorHeatmapResponse(BaseModel):
    sectors: list[SectorPerformanceOut]


class TapeQuoteOut(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float


class TickerTapeResponse(BaseModel):
    quotes: list[TapeQuoteOut]