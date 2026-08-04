"""
Quantitative analytics engine — pure computation, no I/O.

Takes a pandas price Series and returns a QuantSnapshot with all signal
metrics. Same separation philosophy as core/dcf.py: deterministic,
unit-testable, data-source agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class QuantSnapshot:
    """All quant signal outputs for a single ticker."""

    ticker: str
    current_price: float

    # Cross-timeframe momentum (risk-adjusted return / annualised vol)
    momentum_20d: float | None
    momentum_60d: float | None
    momentum_252d: float | None

    # Rolling Sharpe ratio (annualised)
    sharpe_60d: float | None
    sharpe_252d: float | None

    # Beta vs benchmark
    beta: float | None

    # Realised volatility surface (annualised)
    vol_10d: float | None
    vol_30d: float | None
    vol_60d: float | None
    vol_252d: float | None

    # RSI (14-period, Wilder's smoothing)
    rsi: float | None

    # Bollinger Bands (20d, 2σ)
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    bb_pct_b: float | None  # 0 = at lower band, 1 = at upper band


# ── internal helpers ─────────────────────────────────────────────────────────

def _safe(val: float) -> float | None:
    """Return None for NaN / inf, otherwise round to 4dp."""
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return None
    return round(float(val), 4)


def _momentum_score(prices: pd.Series, window: int) -> float | None:
    """
    Risk-adjusted momentum: period_return / annualised_vol.
    Normalises raw return by risk so cross-window scores are comparable.
    """
    if len(prices) < window + 1:
        return None
    period_return = float(prices.iloc[-1] / prices.iloc[-window] - 1)
    daily_returns = prices.pct_change().dropna()
    if len(daily_returns) < window:
        return None
    vol = float(daily_returns.iloc[-window:].std()) * np.sqrt(252)
    if vol == 0:
        return None
    return _safe(period_return / vol)


def _rolling_sharpe(daily_returns: pd.Series, window: int, risk_free_rate: float) -> float | None:
    if len(daily_returns) < window:
        return None
    recent = daily_returns.iloc[-window:]
    excess = float(recent.mean()) * 252 - risk_free_rate
    vol = float(recent.std()) * np.sqrt(252)
    if vol == 0:
        return None
    return _safe(excess / vol)


def _beta(stock_returns: pd.Series, bench_returns: pd.Series, window: int = 252) -> float | None:
    aligned = pd.concat([stock_returns, bench_returns], axis=1).dropna()
    aligned.columns = ["stock", "bench"]
    n = min(window, len(aligned))
    if n < 30:
        return None
    recent = aligned.iloc[-n:]
    var_bench = float(recent["bench"].var())
    if var_bench == 0:
        return None
    cov = float(recent["stock"].cov(recent["bench"]))
    return _safe(cov / var_bench)


def _realized_vol(daily_returns: pd.Series, window: int) -> float | None:
    if len(daily_returns) < window:
        return None
    return _safe(float(daily_returns.iloc[-window:].std()) * np.sqrt(252))


def _rsi(prices: pd.Series, period: int = 14) -> float | None:
    """RSI using Wilder's smoothing (standard Bloomberg / FactSet method)."""
    if len(prices) < period + 1:
        return None
    delta = prices.diff().dropna()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)

    avg_gain = float(gains.iloc[:period].mean())
    avg_loss = float(losses.iloc[:period].mean())

    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + float(gains.iloc[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses.iloc[i])) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return _safe(100 - (100 / (1 + rs)))


def _bollinger(prices: pd.Series, window: int = 20, num_std: float = 2.0):
    if len(prices) < window:
        return None, None, None, None
    recent = prices.iloc[-window:]
    middle = float(recent.mean())
    std = float(recent.std())
    upper = middle + num_std * std
    lower = middle - num_std * std
    current = float(prices.iloc[-1])
    pct_b = (current - lower) / (upper - lower) if upper != lower else 0.5
    return _safe(upper), _safe(middle), _safe(lower), _safe(pct_b)


# ── public API ────────────────────────────────────────────────────────────────

def compute_quant_snapshot(
    ticker: str,
    prices: pd.Series,
    benchmark_prices: pd.Series | None = None,
    risk_free_rate: float = 0.042,
) -> QuantSnapshot:
    """
    Compute all quant metrics from a daily Close price series.

    prices: pd.Series with DatetimeIndex, daily Close prices
    benchmark_prices: benchmark Close prices for beta (optional; beta=None if absent)
    """
    daily_returns = prices.pct_change().dropna()

    bench_returns: pd.Series = (
        benchmark_prices.pct_change().dropna()
        if benchmark_prices is not None and len(benchmark_prices) > 1
        else pd.Series(dtype=float)
    )

    bb_upper, bb_middle, bb_lower, bb_pct_b = _bollinger(prices)

    return QuantSnapshot(
        ticker=ticker,
        current_price=round(float(prices.iloc[-1]), 2),
        momentum_20d=_momentum_score(prices, 20),
        momentum_60d=_momentum_score(prices, 60),
        momentum_252d=_momentum_score(prices, 252),
        sharpe_60d=_rolling_sharpe(daily_returns, 60, risk_free_rate),
        sharpe_252d=_rolling_sharpe(daily_returns, 252, risk_free_rate),
        beta=_beta(daily_returns, bench_returns) if len(bench_returns) > 0 else None,
        vol_10d=_realized_vol(daily_returns, 10),
        vol_30d=_realized_vol(daily_returns, 30),
        vol_60d=_realized_vol(daily_returns, 60),
        vol_252d=_realized_vol(daily_returns, 252),
        rsi=_rsi(prices),
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        bb_pct_b=bb_pct_b,
    )


def benchmark_for_ticker(symbol: str) -> str:
    """Return the appropriate benchmark ticker for beta computation."""
    upper = symbol.upper()
    if upper.endswith(".NS") or upper.endswith(".BO"):
        return "^NSEI"
    if any(upper.endswith(ext) for ext in [".DE", ".L", ".PA", ".AS", ".MI", ".MC", ".BR", ".SW"]):
        return "^STOXX50E"
    return "^GSPC"

def compute_signal_bias(
    momentum_20d: float | None,
    momentum_60d: float | None,
    momentum_252d: float | None,
    sharpe_252d: float | None,
    rsi: float | None,
    bb_pct_b: float | None,
) -> str:
    """
    Compute an overall directional Signal Bias using a weighted multi-factor
    scoring system. Using a score threshold (not a single hard cutoff) provides
    natural hysteresis — the label only flips when multiple signals align,
    preventing oscillation from noise in a single metric near its boundary.

    Score weights:
      252d momentum: ±2  (strongest trend signal, longest lookback)
      60d momentum:  ±1  (medium-term confirmation)
      20d momentum:  ±1  (short-term, most noise — lowest weight)
      Sharpe 252d:   ±1  (risk-adjusted quality gate)
      RSI extreme:   ±1  (overbought/oversold, only at extremes)

    Label thresholds (hysteresis via score, not single-metric cutoff):
      score >= 3  → BULLISH
      score <= -3 → BEARISH
      else        → NEUTRAL
    """
    BULLISH_THRESHOLD = 3
    BEARISH_THRESHOLD = -3

    score = 0.0

    # 252d momentum — weight 2 (longest lookback, most reliable)
    if momentum_252d is not None:
        if momentum_252d > 0.5:
            score += 2
        elif momentum_252d > 0.3:
            score += 1
        elif momentum_252d < -0.5:
            score -= 2
        elif momentum_252d < -0.3:
            score -= 1

    # 60d momentum — weight 1
    if momentum_60d is not None:
        if momentum_60d > 0.3:
            score += 1
        elif momentum_60d < -0.3:
            score -= 1

    # 20d momentum — weight 1 (noisiest; only counts at extremes)
    if momentum_20d is not None:
        if momentum_20d > 0.5:
            score += 1
        elif momentum_20d < -0.5:
            score -= 1

    # 252d Sharpe — quality gate: strong positive return adds, negative removes
    if sharpe_252d is not None:
        if sharpe_252d > 1.5:
            score += 1
        elif sharpe_252d < 0:
            score -= 1

    # RSI — only at genuine extremes (<25 or >75), avoids penalising mid-range
    if rsi is not None:
        if rsi < 25:
            score += 1   # oversold — potential reversal
        elif rsi > 75:
            score -= 1   # overbought — momentum risk

    if score >= BULLISH_THRESHOLD:
        return "BULLISH"
    elif score <= BEARISH_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"