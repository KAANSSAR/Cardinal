"""Comparable companies computation engine — pure computation, no I/O."""
from __future__ import annotations
from dataclasses import dataclass
import statistics


@dataclass(frozen=True)
class PeerMetrics:
    ticker: str
    name: str
    market_cap: float | None
    enterprise_value: float | None
    ev_ebitda: float | None
    pe_ratio: float | None
    ev_revenue: float | None
    ps_ratio: float | None
    revenue_ttm: float | None
    ebitda_ttm: float | None


@dataclass(frozen=True)
class CompsResult:
    target: str
    peers: list[PeerMetrics]
    median_ev_ebitda: float | None
    median_pe: float | None
    median_ev_revenue: float | None
    median_ps: float | None
    implied_ev_from_ebitda: float | None
    implied_ev_from_revenue: float | None
    implied_price_from_pe: float | None
    implied_price_from_ps: float | None


def _median(values: list) -> float | None:
    valid = [v for v in values if v is not None and v > 0]
    if not valid:
        return None
    return statistics.median(valid)


def compute_comps(target_ticker: str, target_metrics: PeerMetrics, peers: list[PeerMetrics]) -> CompsResult:
    all_peers = [p for p in peers if p.ticker != target_ticker]
    median_ev_ebitda = _median([p.ev_ebitda for p in all_peers])
    median_pe = _median([p.pe_ratio for p in all_peers])
    median_ev_revenue = _median([p.ev_revenue for p in all_peers])
    median_ps = _median([p.ps_ratio for p in all_peers])
    implied_ev_from_ebitda = (
        median_ev_ebitda * target_metrics.ebitda_ttm
        if median_ev_ebitda is not None and target_metrics.ebitda_ttm is not None and target_metrics.ebitda_ttm > 0
        else None
    )
    implied_ev_from_revenue = (
        median_ev_revenue * target_metrics.revenue_ttm
        if median_ev_revenue is not None and target_metrics.revenue_ttm is not None
        else None
    )
    return CompsResult(
        target=target_ticker, peers=all_peers,
        median_ev_ebitda=median_ev_ebitda, median_pe=median_pe,
        median_ev_revenue=median_ev_revenue, median_ps=median_ps,
        implied_ev_from_ebitda=implied_ev_from_ebitda,
        implied_ev_from_revenue=implied_ev_from_revenue,
        implied_price_from_pe=None, implied_price_from_ps=None,
    )