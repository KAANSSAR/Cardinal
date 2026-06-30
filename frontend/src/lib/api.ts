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

export interface DCFAssumptions {
  growth_rate: number;
  terminal_growth_rate: number;
  projection_years: number;
  wacc_override?: number;
}

export function fetchDCF(ticker: string, assumptions: Partial<DCFAssumptions> = {}) {
  const params: Record<string, string | number> = {};
  if (assumptions.growth_rate !== undefined) params.growth_rate = assumptions.growth_rate;
  if (assumptions.terminal_growth_rate !== undefined)
    params.terminal_growth_rate = assumptions.terminal_growth_rate;
  if (assumptions.projection_years !== undefined)
    params.projection_years = assumptions.projection_years;
  if (assumptions.wacc_override !== undefined) params.wacc_override = assumptions.wacc_override;

  return apiGet<DCFResponse>(`/ticker/${ticker}/dcf`, params);
}
