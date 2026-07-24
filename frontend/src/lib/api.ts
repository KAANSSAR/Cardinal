const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, String(value));
    }
  }
  const response = await fetch(url.toString());
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail ?? "Request failed", response.status);
  }
  return response.json() as Promise<T>;
}

// ── DCF ──────────────────────────────────────────────────────────────────────

export interface DCFAssumptions {
  growth_rate: number;
  terminal_growth_rate: number;
  projection_years: number;
  wacc_override?: number;
}

export interface DCFResponse {
  ticker: string;
  company_name: string;
  wacc: number;
  cost_of_equity: number;
  projected_fcf: number[];
  pv_projected_fcf: number[];
  pv_terminal_value: number;
  terminal_value_pct_of_ev: number;
  enterprise_value: number;
  equity_value: number;
  intrinsic_value_per_share: number;
  current_price: number;
  premium_discount_pct: number;
}

export function fetchDCF(ticker: string, assumptions: Partial<DCFAssumptions> = {}) {
  const params: Record<string, string | number> = {};
  if (assumptions.growth_rate !== undefined) params.growth_rate = assumptions.growth_rate;
  if (assumptions.terminal_growth_rate !== undefined) params.terminal_growth_rate = assumptions.terminal_growth_rate;
  if (assumptions.projection_years !== undefined) params.projection_years = assumptions.projection_years;
  if (assumptions.wacc_override !== undefined) params.wacc_override = assumptions.wacc_override;
  return apiGet<DCFResponse>(`/ticker/${ticker}/dcf`, params);
}

// ── Comps ─────────────────────────────────────────────────────────────────────

export interface PeerMetrics {
  ticker: string;
  name: string;
  market_cap: number | null;
  enterprise_value: number | null;
  ev_ebitda: number | null;
  pe_ratio: number | null;
  ev_revenue: number | null;
  ps_ratio: number | null;
}

export interface CompsResponse {
  ticker: string;
  peers: PeerMetrics[];
  median_ev_ebitda: number | null;
  median_pe: number | null;
  median_ev_revenue: number | null;
  median_ps: number | null;
  implied_ev_from_ebitda: number | null;
  implied_ev_from_revenue: number | null;
}

export function fetchComps(ticker: string) {
  return apiGet<CompsResponse>(`/ticker/${ticker}/comps`);
}

// ── Search ────────────────────────────────────────────────────────────────────

export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string | null;
  type: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export function searchTickers(query: string) {
  return apiGet<SearchResponse>("/search", { q: query });
}

// ── Quant ─────────────────────────────────────────────────────────────────────

export interface QuantResponse {
  ticker: string;
  current_price: number;
  benchmark: string;
  momentum_20d: number | null;
  momentum_60d: number | null;
  momentum_252d: number | null;
  sharpe_60d: number | null;
  sharpe_252d: number | null;
  beta: number | null;
  vol_10d: number | null;
  vol_30d: number | null;
  vol_60d: number | null;
  vol_252d: number | null;
  rsi: number | null;
  bb_upper: number | null;
  bb_middle: number | null;
  bb_lower: number | null;
  bb_pct_b: number | null;
}

export function fetchQuant(ticker: string) {
  return apiGet<QuantResponse>(`/ticker/${ticker}/quant`);
}

// ── Backtest ──────────────────────────────────────────────────────────────────

export interface CurvePoint {
  date: string;
  value: number;
}

export interface BacktestResponse {
  ticker: string;
  strategy: string;
  params: Record<string, number>;
  total_return: number;
  buy_hold_return: number;
  sharpe: number | null;
  max_drawdown: number;
  win_rate: number | null;
  num_trades: number;
  avg_win: number | null;
  avg_loss: number | null;
  pnl_curve: CurvePoint[];
  buy_hold_curve: CurvePoint[];
}

export type BacktestStrategy = "momentum" | "mean_reversion";

export function fetchBacktest(
  ticker: string,
  strategy: BacktestStrategy = "momentum",
  params: Record<string, number> = {}
) {
  return apiGet<BacktestResponse>(`/ticker/${ticker}/backtest`, { strategy, ...params });
}