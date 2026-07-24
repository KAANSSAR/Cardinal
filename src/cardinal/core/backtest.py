"""
Algorithmic backtest engine — pure computation, no I/O.

Two built-in strategies:
  A) Momentum   — Golden Cross / Death Cross (50d vs 200d MA)
  B) Mean Reversion — Buy when price drops >N sigma below rolling mean

Same separation as core/dcf.py: takes a price Series, returns a typed
result. No external calls, fully deterministic, unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    ticker: str
    strategy: str
    params: dict

    # Scalar performance metrics
    total_return: float        # strategy total return
    buy_hold_return: float     # passive buy-and-hold over same period
    sharpe: float | None       # annualised Sharpe of trade returns
    max_drawdown: float        # worst peak-to-trough (negative number)
    win_rate: float | None     # fraction of trades that were profitable
    num_trades: int
    avg_win: float | None      # average return of winning trades
    avg_loss: float | None     # average return of losing trades

    # Time series for charts (sampled to keep payload manageable)
    pnl_curve: list[dict]       # [{"date": "2021-01-04", "value": 1.0}, ...]
    buy_hold_curve: list[dict]


# ── helpers ───────────────────────────────────────────────────────────────────

def _max_drawdown(curve: list[float]) -> float:
    peak = curve[0]
    max_dd = 0.0
    for val in curve:
        if val > peak:
            peak = val
        dd = (val - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _annualised_sharpe(trade_returns: list[float], risk_free_rate: float) -> float | None:
    """
    Compute Sharpe from individual trade returns (not daily returns).
    Annualise by assuming 252 trading days.
    """
    if len(trade_returns) < 2:
        return None
    arr = np.array(trade_returns)
    mean_daily = arr.mean()
    std_daily = arr.std()
    if std_daily == 0:
        return None
    sharpe = (mean_daily * 252 - risk_free_rate) / (std_daily * np.sqrt(252))
    return round(float(sharpe), 4)


def _build_curves(
    dates: pd.DatetimeIndex,
    portfolio_curve: list[float],
    buy_hold_curve: list[float],
    max_points: int = 500,
) -> tuple[list[dict], list[dict]]:
    """
    Downsample to max_points for a manageable JSON payload.
    5 years of daily data = ~1260 points; 500 gives a smooth chart.
    """
    n = len(dates)
    step = max(1, n // max_points)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)

    pnl = [{"date": str(dates[i].date()), "value": round(portfolio_curve[i], 6)} for i in indices]
    bh = [{"date": str(dates[i].date()), "value": round(buy_hold_curve[i], 6)} for i in indices]
    return pnl, bh


# ── strategy A: momentum ──────────────────────────────────────────────────────

def run_momentum_backtest(
    ticker: str,
    prices: pd.Series,
    fast_window: int = 50,
    slow_window: int = 200,
    commission: float = 0.001,
    risk_free_rate: float = 0.042,
) -> BacktestResult:
    """
    Golden Cross / Death Cross.
    Entry: fast MA crosses above slow MA.
    Exit:  fast MA crosses below slow MA.
    """
    if len(prices) < slow_window + 10:
        raise ValueError(
            f"Need at least {slow_window + 10} trading days — got {len(prices)}. "
            "Try a longer price history period."
        )

    fast_ma = prices.rolling(fast_window).mean()
    slow_ma = prices.rolling(slow_window).mean()
    signal = (fast_ma > slow_ma).astype(int)

    portfolio = 1.0
    position = 0
    entry_price = 0.0
    portfolio_curve: list[float] = []
    trade_returns: list[float] = []

    for i in range(len(prices)):
        portfolio_curve.append(portfolio)
        if i == 0:
            continue

        cur_sig = int(signal.iloc[i]) if not pd.isna(signal.iloc[i]) else 0
        prev_sig = int(signal.iloc[i - 1]) if not pd.isna(signal.iloc[i - 1]) else 0
        price = float(prices.iloc[i])

        if cur_sig == 1 and prev_sig == 0 and position == 0:
            position = 1
            entry_price = price * (1 + commission)

        elif cur_sig == 0 and prev_sig == 1 and position == 1:
            exit_price = price * (1 - commission)
            ret = (exit_price - entry_price) / entry_price
            portfolio *= (1 + ret)
            portfolio_curve[-1] = portfolio
            trade_returns.append(ret)
            position = 0

    if position == 1:
        exit_price = float(prices.iloc[-1]) * (1 - commission)
        ret = (exit_price - entry_price) / entry_price
        portfolio *= (1 + ret)
        portfolio_curve[-1] = portfolio
        trade_returns.append(ret)

    bh_start = float(prices.iloc[0])
    buy_hold_curve = [float(p) / bh_start for p in prices]

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]

    pnl, bh = _build_curves(prices.index, portfolio_curve, buy_hold_curve)

    return BacktestResult(
        ticker=ticker,
        strategy="momentum",
        params={"fast_window": fast_window, "slow_window": slow_window, "commission": commission},
        total_return=round(portfolio - 1, 4),
        buy_hold_return=round(buy_hold_curve[-1] - 1, 4),
        sharpe=_annualised_sharpe(trade_returns, risk_free_rate),
        max_drawdown=_max_drawdown(portfolio_curve),
        win_rate=round(len(wins) / len(trade_returns), 4) if trade_returns else None,
        num_trades=len(trade_returns),
        avg_win=round(float(np.mean(wins)), 4) if wins else None,
        avg_loss=round(float(np.mean(losses)), 4) if losses else None,
        pnl_curve=pnl,
        buy_hold_curve=bh,
    )


# ── strategy B: mean reversion ────────────────────────────────────────────────

def run_mean_reversion_backtest(
    ticker: str,
    prices: pd.Series,
    lookback: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    commission: float = 0.001,
    max_hold_days: int = 15,
    risk_free_rate: float = 0.042,
) -> BacktestResult:
    """
    Mean reversion.
    Entry: z-score < -entry_z (price too far below rolling mean).
    Exit:  z-score >= exit_z (price reverted) OR max_hold_days elapsed.
    """
    if len(prices) < lookback + 10:
        raise ValueError(
            f"Need at least {lookback + 10} trading days — got {len(prices)}."
        )

    rolling_mean = prices.rolling(lookback).mean()
    rolling_std = prices.rolling(lookback).std()
    z_score = (prices - rolling_mean) / rolling_std

    portfolio = 1.0
    position = 0
    entry_price = 0.0
    hold_days = 0
    portfolio_curve: list[float] = []
    trade_returns: list[float] = []

    for i in range(len(prices)):
        portfolio_curve.append(portfolio)
        if pd.isna(z_score.iloc[i]):
            continue

        price = float(prices.iloc[i])
        z = float(z_score.iloc[i])

        if position == 0 and z < -entry_z:
            position = 1
            entry_price = price * (1 + commission)
            hold_days = 0

        elif position == 1:
            hold_days += 1
            if z >= exit_z or hold_days >= max_hold_days:
                exit_price = price * (1 - commission)
                ret = (exit_price - entry_price) / entry_price
                portfolio *= (1 + ret)
                portfolio_curve[-1] = portfolio
                trade_returns.append(ret)
                position = 0
                hold_days = 0

    if position == 1:
        exit_price = float(prices.iloc[-1]) * (1 - commission)
        ret = (exit_price - entry_price) / entry_price
        portfolio *= (1 + ret)
        portfolio_curve[-1] = portfolio
        trade_returns.append(ret)

    bh_start = float(prices.iloc[0])
    buy_hold_curve = [float(p) / bh_start for p in prices]

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]

    pnl, bh = _build_curves(prices.index, portfolio_curve, buy_hold_curve)

    return BacktestResult(
        ticker=ticker,
        strategy="mean_reversion",
        params={"lookback": lookback, "entry_z": entry_z, "exit_z": exit_z, "commission": commission},
        total_return=round(portfolio - 1, 4),
        buy_hold_return=round(buy_hold_curve[-1] - 1, 4),
        sharpe=_annualised_sharpe(trade_returns, risk_free_rate),
        max_drawdown=_max_drawdown(portfolio_curve),
        win_rate=round(len(wins) / len(trade_returns), 4) if trade_returns else None,
        num_trades=len(trade_returns),
        avg_win=round(float(np.mean(wins)), 4) if wins else None,
        avg_loss=round(float(np.mean(losses)), 4) if losses else None,
        pnl_curve=pnl,
        buy_hold_curve=bh,
    )