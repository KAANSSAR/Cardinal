# Cardinal

[![CI](https://github.com/KAANSSAR/Cardinal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAANSSAR/Cardinal/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-163%20passing-brightgreen)](https://github.com/KAANSSAR/Cardinal/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multi-lens equity analysis terminal combining fundamental DCF valuation, quantitative signal analytics, algorithmic backtesting, and agentic AI interpretation — for any ticker across US, Indian, and European markets.

## Status — Week 3 of the build plan

| Lens | Status |
|---|---|
| Fundamental (DCF) | ✅ Complete — live sliders, comps table, intrinsic vs current price visual |
| Quant overlay | ✅ Complete — momentum, Sharpe, beta, vol surface, RSI, Bollinger bands |
| Algo backtest | ✅ Complete — momentum (Golden Cross) and mean reversion strategies |
| AI agents (Xavi / Iniesta / Busquets / Messi) | 🚧 Week 4 |

## What's built

**Backend — 163 tests passing**

- `core/dcf.py` — pure DCF engine: CAPM cost of equity, WACC, FCF projection, Gordon Growth terminal value
- `core/comps.py` — comparable companies engine: peer median multiples, implied EV
- `core/quant.py` — quant analytics: momentum (20d/60d/252d), rolling Sharpe (60d/252d), beta vs benchmark, realised vol surface (10d/30d/60d/252d), RSI (14-period, Wilder's smoothing), Bollinger Bands (20d, 2σ)
- `core/backtest.py` — algo backtest: momentum (Golden Cross/Death Cross, configurable MA windows) and mean reversion (σ-based entry/exit, configurable lookback and threshold)
- `data/market_data.py` — yfinance wrapper: price history, EU/India financials, benchmark fetching
- `data/fmp_client.py` — FMP client: profile, income statement, balance sheet, cash flow, stock peers
- `config.py` — environment-based config
- `api/main.py` — eight live endpoints:
  - `GET /health`
  - `GET /search?q=...` — ticker + company name search (Yahoo Finance, free)
  - `GET /ticker/{symbol}/dcf` — full DCF valuation with live assumption params
  - `GET /ticker/{symbol}/comps` — peer companies with EV/EBITDA, P/E, EV/Revenue, P/S
  - `GET /ticker/{symbol}/price-history` — OHLCV via yfinance
  - `GET /ticker/{symbol}/quant` — full quant signal snapshot
  - `GET /ticker/{symbol}/backtest?strategy=momentum|mean_reversion` — P&L curve, Sharpe, drawdown, win rate
  - `GET /ticker/{symbol}/income-statement` — via FMP
  - `GET /ticker/{symbol}/balance-sheet` — via FMP

**Frontend — Vite + React 19 + TypeScript + Tailwind v4**

Three fully active tabs on every ticker page:

- **Fundamental** — live WACC/growth/terminal value sliders (debounced), DCF output card with intrinsic vs current price visual bar, comparable companies table with colour-coded multiples and clickable peer tickers
- **Quant** — signal dashboard table (metric, value, interpretation, signal badge), volatility surface (10d/30d/60d/252d annualised), Bollinger band levels. Loads automatically on tab click.
- **Backtest** — strategy selector (Momentum / Mean Reversion), configurable sliders (MA windows, σ threshold), metrics grid (Sharpe, max drawdown, win rate, avg win/loss, trade count), P&L curve vs buy-and-hold chart (Recharts), outperformance callout. On-demand via Run button.

Search autocomplete — type by ticker OR company name, dropdown with keyboard navigation.

**Infra**

- Dockerfile + docker-compose (backend + frontend)
- GitHub Actions CI — Python 3.10–3.12 test matrix + frontend type-check/build

## Project Structure

```
Cardinal/
├── src/cardinal/
│   ├── core/
│   │   ├── dcf.py                 # DCF valuation engine
│   │   ├── comps.py               # Comparable companies engine
│   │   ├── quant.py               # Quant analytics engine
│   │   └── backtest.py            # Algo backtest engine
│   ├── data/
│   │   ├── market_data.py         # yfinance wrapper
│   │   ├── fmp_client.py          # Financial Modeling Prep client
│   │   └── utils.py
│   ├── api/
│   │   ├── main.py                # FastAPI app + all routes
│   │   └── models.py              # Pydantic models
│   └── config.py
├── frontend/src/
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── TickerSearch.tsx       # Autocomplete search
│   │   ├── AssumptionsPanel.tsx   # DCF sliders
│   │   ├── DCFOutputCard.tsx      # DCF output + visual bar
│   │   ├── CompsTable.tsx         # Peer multiples table
│   │   ├── QuantDashboard.tsx     # Signal table + vol surface
│   │   └── BacktestView.tsx       # Strategy config + P&L chart
│   ├── pages/
│   │   ├── Home.tsx
│   │   └── TickerPage.tsx         # Three-tab layout
│   └── lib/
│       ├── api.ts                 # Typed backend client
│       └── useDebounce.ts
├── tests/                         # 163 tests across 6 files
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Quickstart

**Backend:**
```bash
git clone https://github.com/KAANSSAR/Cardinal.git
cd Cardinal
cp .env.example .env   # add FMP_API_KEY
pip install -e ".[dev]"
pytest tests/ -v        # 163 passing
uvicorn cardinal.api.main:app --reload
# http://localhost:8000/docs
```

**Frontend:**
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
# http://localhost:5173
```

**Docker:**
```bash
docker compose up
```

## Agent architecture (Week 4)

Cardinal's AI sidebar will house four specialist agents named after the Barça midfield:

| Agent | Lens | Persona | Output |
|---|---|---|---|
| **Xavi** | Fundamental | IB Analyst | Investment memo: bull case, bear case, valuation verdict |
| **Iniesta** | Quant | Desk Quant | Signal summary: directional bias, confidence, timing commentary |
| **Busquets** | Backtest | Strategy Reviewer | Strategy verdict, regime observations, parameter refinements |
| **Messi** | Synthesis | Portfolio Manager | Final buy / hold / sell verdict across all three lenses |

Agents are strictly read-only — they receive a frozen JSON snapshot of Cardinal's computed outputs and cannot modify any data. Powered by Google Gemini 2.5 Flash. News context via Tavily (headlines only, cannot override Cardinal's figures). Delivered via a closeable sidebar with tabs per agent and a freeform chat input.

## Why this exists

Bloomberg Terminal costs $24,000/year. No open tool combines DCF valuation, quant signal analytics, and algorithmic backtesting in a single interface with global market coverage. Cardinal closes that gap — with a full-stack deployment, CI/CD, and an agentic AI layer that mirrors what major bank internal AI teams are actively building.