# Cardinal

[![CI](https://github.com/KAANSSAR/Cardinal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAANSSAR/Cardinal/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-231%20passing-brightgreen)](https://github.com/KAANSSAR/Cardinal/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multi-lens equity analysis terminal combining fundamental DCF valuation, quantitative signal analytics, algorithmic backtesting, and agentic AI interpretation — for any ticker across US, Indian, and European markets.

## Status — Week 4 complete

| Lens | Status |
|---|---|
| Fundamental (DCF) | ✅ Live sliders, comps table, intrinsic vs current price visual |
| Quant overlay | ✅ Momentum, Sharpe, beta, vol surface, RSI, Bollinger bands |
| Algo backtest | ✅ Momentum (Golden Cross) and mean reversion strategies |
| AI agents (Xavi / Iniesta / Busquets / Messi) | ✅ Full agent team, sidebar, Messi chat |

## What's built

**Backend — 231 tests passing**

- `core/dcf.py` — pure DCF engine: CAPM cost of equity, WACC, FCF projection, Gordon Growth terminal value
- `core/comps.py` — comparable companies engine: peer median multiples, implied EV
- `core/quant.py` — quant analytics: momentum (20d/60d/252d), rolling Sharpe (60d/252d), beta vs benchmark, realised vol surface (10d/30d/60d/252d), RSI (14-period, Wilder's smoothing), Bollinger Bands (20d, 2σ)
- `core/backtest.py` — algo backtest: momentum (Golden Cross/Death Cross) and mean reversion (σ-based entry/exit), configurable parameters
- `agents/gemini_client.py` — Gemini 3.5 Flash client, thinking disabled, 2048 token output budget
- `agents/xavi.py` — Fundamental Analyst: DCF + comps snapshot → structured IB investment memo
- `agents/iniesta.py` — Quant Analyst: quant signal snapshot → directional bias with timing commentary
- `agents/busquets.py` — Strategy Reviewer: backtest snapshot → edge verdict, regime observations, refinements
- `agents/messi.py` — Portfolio Manager: orchestrates the full team, synthesises BUY/HOLD/SELL verdict, follow-up chat with guardrails
- `agents/cache.py` — in-memory TTL cache (1hr) keyed by agent + ticker + params; Messi checks each agent's cache before re-running
- `agents/news.py` — Tavily news context (3 headlines, graceful degradation if key absent)
- `data/market_data.py` — yfinance wrapper: price history, EU/India financials, benchmark fetching
- `data/fmp_client.py` — FMP client: profile, income statement, balance sheet, cash flow, stock peers
- `config.py` — environment-based config (FMP, Gemini, Tavily keys)
- `api/main.py` — 13 live endpoints:
  - `GET /health`
  - `GET /search?q=...` — ticker + company name search (Yahoo Finance, no key required)
  - `GET /ticker/{symbol}/dcf` — full DCF valuation with live assumption params
  - `GET /ticker/{symbol}/comps` — peer companies with EV/EBITDA, P/E, EV/Revenue, P/S
  - `GET /ticker/{symbol}/price-history` — OHLCV via yfinance
  - `GET /ticker/{symbol}/quant` — full quant signal snapshot
  - `GET /ticker/{symbol}/backtest` — P&L curve, Sharpe, drawdown, win rate
  - `GET /ticker/{symbol}/income-statement` — via FMP
  - `GET /ticker/{symbol}/balance-sheet` — via FMP
  - `POST /agent/xavi` — fundamental analyst memo (cached)
  - `POST /agent/iniesta` — quant signal memo (cached)
  - `POST /agent/busquets` — backtest strategy memo (cached)
  - `POST /agent/messi` — orchestrates all three agents, synthesises verdict, returns all four memos
  - `POST /agent/messi/chat` — Messi follow-up chat with memo context, Tavily news, strict guardrails

**Frontend — Vite + React 19 + TypeScript + Tailwind v4**

Four tabs on every ticker page — Fundamental, Quant, Backtest, AI:

- **Fundamental** — live WACC/growth/terminal value sliders (debounced), DCF output card with intrinsic vs current price visual, comparable companies table with colour-coded multiples and clickable peer tickers
- **Quant** — signal dashboard (metric, value, interpretation, signal badge), volatility surface, Bollinger band levels
- **Backtest** — strategy selector, configurable sliders, metrics grid, P&L curve vs buy-and-hold (Recharts)
- **AI sidebar** — slides in from the right, pushing content left; four agent tabs (Xavi / Iniesta / Busquets / Messi); per-agent empty states with descriptions; cache dot shows which agents were served from cache; news badge when Tavily context was included; Messi tab includes full bubble chat UI with history

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
│   ├── agents/
│   │   ├── gemini_client.py       # Gemini 3.5 Flash wrapper
│   │   ├── xavi.py                # Fundamental Analyst agent
│   │   ├── iniesta.py             # Quant Analyst agent
│   │   ├── busquets.py            # Strategy Reviewer agent
│   │   ├── messi.py               # Portfolio Manager agent + chat
│   │   ├── cache.py               # In-memory TTL agent cache
│   │   └── news.py                # Tavily news context fetcher
│   ├── data/
│   │   ├── market_data.py
│   │   ├── fmp_client.py
│   │   └── utils.py
│   ├── api/
│   │   ├── main.py                # FastAPI app + all routes
│   │   └── models.py              # Pydantic request/response models
│   └── config.py
├── frontend/src/
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── TickerSearch.tsx       # Autocomplete — search by ticker or company name
│   │   ├── AssumptionsPanel.tsx   # DCF sliders
│   │   ├── DCFOutputCard.tsx      # DCF output + intrinsic vs current price bar
│   │   ├── CompsTable.tsx         # Peer multiples + clickable tickers
│   │   ├── QuantDashboard.tsx     # Signal table + vol surface
│   │   ├── BacktestView.tsx       # Strategy config + P&L chart
│   │   └── AISidebar.tsx          # AI panel — four agent tabs + Messi chat
│   ├── pages/
│   │   ├── Home.tsx
│   │   └── TickerPage.tsx         # Four-tab layout with sidebar
│   └── lib/
│       ├── api.ts                 # Typed backend client
│       └── useDebounce.ts
├── tests/                         # 231 tests across 8 files
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
cp .env.example .env   # add FMP_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY
pip install -e ".[dev]"
pytest tests/ -v        # 231 passing
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

## Agent architecture

Four specialist agents named after the Barça midfield — each reads Cardinal's computed data as a frozen, read-only snapshot and cannot modify anything:

| Agent | Lens | Persona | Output |
|---|---|---|---|
| **Xavi** | Fundamental | IB Analyst | Investment memo: valuation verdict, bull/bear case, key risks, peer comparison |
| **Iniesta** | Quant | Desk Quant | Signal summary: directional bias, momentum analysis, vol regime, timing call |
| **Busquets** | Backtest | Strategy Reviewer | Strategy verdict, regime observations, suggested refinements, risk flag |
| **Messi** | Synthesis | Portfolio Manager | BUY / HOLD / SELL verdict across all three lenses + follow-up chat |

**Orchestration:** `POST /agent/messi` runs Xavi → Iniesta → Busquets sequentially then synthesises. Each agent's memo is cached for 1 hour — a second Messi call on the same ticker with unchanged params skips re-running the cached agents and only runs the synthesis, cutting response time from ~18s to ~4s.

**Guardrails (all agents):**
- Agents may only draw conclusions from Cardinal's computed data
- News context (Tavily, 3 headlines) adds background only — cannot override any computed figure
- No personalised financial advice, no position sizing recommendations
- Messi chat enforces 7 additional rules: no fabricated numbers, no verdict changes to please the user, explicit refusals for out-of-scope questions

**Powered by:** Google Gemini 3.5 Flash (thinking disabled for clean structured output), Tavily for news context.

## Why this exists

Bloomberg Terminal costs $24,000/year. No open tool combines DCF valuation, quant signal analytics, and algorithmic backtesting in a single interface with global market coverage. Cardinal closes that gap — with production-grade architecture, CI/CD, and an agentic AI layer that mirrors what major bank internal AI teams are actively building.