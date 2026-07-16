# Cardinal

[![CI](https://github.com/KAANSSAR/Cardinal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAANSSAR/Cardinal/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-122%20passing-brightgreen)](https://github.com/KAANSSAR/Cardinal/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multi-lens equity analysis terminal combining fundamental DCF valuation, quantitative signal analytics, algorithmic backtesting, and agentic AI interpretation — for any ticker across US, Indian, and European markets.

## Status — Week 2 of the build plan

| Lens | Status |
|---|---|
| Fundamental (DCF) | ✅ Complete — live sliders, comps table, intrinsic vs current price visual |
| Quant overlay | 🚧 Week 3 |
| Algo backtest | 🚧 Week 3 |
| AI agents (Xavi / Iniesta / Busquets / Messi) | 🚧 Week 4 |
| Frontend | ✅ DCF view complete — sliders, comps, search autocomplete |

## What's built

**Backend — 122 tests passing, 99% coverage**

- `core/dcf.py` — pure DCF engine: CAPM cost of equity, WACC, FCF projection, Gordon Growth terminal value
- `core/comps.py` — comparable companies engine: peer median multiples, implied EV from EBITDA and revenue
- `data/market_data.py` — yfinance wrapper for price history and EU/India financials
- `data/fmp_client.py` — Financial Modeling Prep client (profile, income statement, balance sheet, cash flow, stock peers)
- `data/utils.py` — shared parsing helpers
- `config.py` — environment-based config loading
- `api/main.py` — six live endpoints:
  - `GET /health`
  - `GET /search?q=...` — ticker + company name search via Yahoo Finance (free, no key needed)
  - `GET /ticker/{symbol}/dcf` — full DCF valuation with live assumption params
  - `GET /ticker/{symbol}/comps` — peer companies with EV/EBITDA, P/E, EV/Revenue, P/S
  - `GET /ticker/{symbol}/price-history` — OHLCV via yfinance
  - `GET /ticker/{symbol}/income-statement` — via FMP
  - `GET /ticker/{symbol}/balance-sheet` — via FMP

**Frontend — Vite + React 19 + TypeScript + Tailwind v4**

- `TickerSearch` — autocomplete dropdown, search by ticker OR company name, keyboard navigation
- `AssumptionsPanel` — four live sliders (FCF growth, terminal growth, WACC override, projection years) with 400ms debounce
- `DCFOutputCard` — full DCF breakdown with intrinsic vs current price visual bar (teal/red/green markers)
- `CompsTable` — peer multiples table, colour-coded cells (red = premium to median, green = discount), peer median row, implied EV callouts, clickable peer tickers that navigate to their own analysis page
- `useDebounce` hook

**Infra**

- Dockerfile + docker-compose (backend + frontend)
- GitHub Actions CI — Python 3.10–3.12 test matrix + frontend type-check/build

## Project Structure

```
Cardinal/
├── src/cardinal/
│   ├── core/
│   │   ├── dcf.py                 # DCF valuation engine (pure computation)
│   │   └── comps.py               # Comparable companies engine
│   ├── data/
│   │   ├── market_data.py         # yfinance wrapper
│   │   ├── fmp_client.py          # Financial Modeling Prep client
│   │   └── utils.py               # shared parsing helpers
│   ├── api/
│   │   ├── main.py                # FastAPI app + all routes
│   │   └── models.py              # Pydantic request/response models
│   └── config.py                  # env-based settings
├── frontend/src/
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── TickerSearch.tsx       # autocomplete search
│   │   ├── AssumptionsPanel.tsx   # live DCF sliders
│   │   ├── DCFOutputCard.tsx      # DCF output + visual bar
│   │   └── CompsTable.tsx         # peer multiples table
│   ├── pages/
│   │   ├── Home.tsx
│   │   └── TickerPage.tsx
│   └── lib/
│       ├── api.ts                 # typed backend client
│       └── useDebounce.ts
├── tests/                         # 122 tests across 5 files
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## Quickstart

**Backend:**
```bash
git clone https://github.com/KAANSSAR/Cardinal.git
cd Cardinal
cp .env.example .env   # add FMP_API_KEY
pip install -e ".[dev]"
pytest tests/ -v        # 122 passing
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

| Agent | Role | Persona |
|---|---|---|
| **Xavi** | Fundamental Agent | IB Analyst — reads DCF output, produces investment memo |
| **Iniesta** | Quant Agent | Desk Quant — reads momentum/Sharpe/vol signals |
| **Busquets** | Backtest Agent | Strategy Reviewer — reads P&L, drawdown, win rate |
| **Messi** | Synthesis Agent | Portfolio Manager — produces final buy/hold/sell verdict |

Agents are strictly read-only — they receive a frozen JSON snapshot of Cardinal's computed outputs and cannot modify any data or assumptions. Powered by Google Gemini 2.5 Flash. News context via Tavily (headlines only, cannot override Cardinal's figures).

## Why this exists

Bloomberg Terminal costs $24,000/year. No open tool combines DCF valuation, quant signal analysis, and algorithmic backtesting in a single interface. Cardinal closes that gap — with a full-stack deployment, CI/CD, and an agentic AI layer that mirrors what major bank internal AI teams are actively building.