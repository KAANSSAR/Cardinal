# Cardinal

[![CI](https://github.com/KAANSSAR/Cardinal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAANSSAR/Cardinal/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-96%20passing-brightgreen)](https://github.com/KAANSSAR/Cardinal/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multi-lens equity analysis terminal combining fundamental DCF valuation, quantitative signal analytics, algorithmic backtesting, and agentic AI interpretation — for any ticker across US, Indian, and European markets.

## Status — Week 1 of the build plan

| Lens | Status |
|---|---|
| Fundamental (DCF) | ✅ Backend complete — live WACC, editable assumptions, FMP + yfinance data layer |
| Quant overlay | 🚧 Week 3 |
| Algo backtest | 🚧 Week 3 |
| AI agents (Xavi / Iniesta / Busquets / Messi) | 🚧 Week 4 |
| Frontend | 🚧 Routing + ticker search shell built, full DCF UI (sliders, comps) lands Week 2 |

## What's built so far

**Backend — fully tested, 96 tests passing, 99% coverage**

- `core/dcf.py` — pure DCF computation: CAPM cost of equity, WACC, FCF projection, Gordon Growth terminal value. No I/O, fully deterministic.
- `data/market_data.py` — yfinance wrapper for price history and EU/India fallback financials.
- `data/fmp_client.py` — Financial Modeling Prep client (primary US fundamentals: profile, income statement, balance sheet, cash flow). Built against FMP's current `stable` endpoint scheme.
- `data/utils.py` — shared parsing helpers used by both data sources.
- `config.py` — environment-based config loading (`.env`, never hardcoded keys).
- `api/main.py` — five live endpoints:
  - `GET /health`
  - `GET /ticker/{symbol}/dcf` — full DCF valuation, query params map to frontend sliders
  - `GET /ticker/{symbol}/price-history` — OHLCV via yfinance
  - `GET /ticker/{symbol}/income-statement` — via FMP
  - `GET /ticker/{symbol}/balance-sheet` — via FMP

**Frontend — Vite + React 19 + TypeScript + Tailwind v4**

- Routing (`/` and `/ticker/:symbol`) via `react-router-dom`
- Layout shell with Cardinal branding (navy header, lens pills) carried over from the project deck's design language
- Ticker search component
- Functional ticker detail page that calls the live DCF endpoint and renders results (full slider UI is a Week 2 item)
- Design tokens (`index.css`) matching the deck's navy/teal/blue/purple/amber palette, Source Serif 4 for display type, Inter for body

**Infra**

- Dockerfile (backend) + docker-compose.yml (backend + frontend)
- GitHub Actions CI — backend test matrix (Python 3.10–3.12) + frontend type-check/build job

## Project Structure

```
Cardinal/
├── src/cardinal/
│   ├── core/dcf.py                # DCF valuation engine (pure computation)
│   ├── data/
│   │   ├── market_data.py         # yfinance wrapper
│   │   ├── fmp_client.py          # Financial Modeling Prep client
│   │   └── utils.py               # shared parsing helpers
│   ├── api/
│   │   ├── main.py                # FastAPI app + routes
│   │   └── models.py              # Pydantic request/response models
│   └── config.py                  # env-based settings
├── frontend/
│   └── src/
│       ├── components/            # Layout, TickerSearch
│       ├── pages/                 # Home, TickerPage
│       └── lib/api.ts             # typed backend client
├── tests/                         # 96 tests across 4 files
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
cp .env.example .env   # fill in your FMP_API_KEY
pip install -e ".[dev]"
pytest tests/ -v        # confirm 96 passing
uvicorn cardinal.api.main:app --reload
# http://localhost:8000/docs for interactive API docs
```

**Frontend:**
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
# http://localhost:5173
```

**Or both via Docker:**
```bash
docker compose up
```

## Why this exists

Bloomberg Terminal costs $24,000/year and combines fundamental data with analytics in a single interface. No open tool does the same for DCF valuation, quant signal analysis, and algorithmic backtesting together. Cardinal aims to close that gap, with a closeable AI sidebar (four agents — Xavi, Iniesta, Busquets, Messi — named after the Barça midfield) that interprets each lens using only Cardinal's own computed data, with strict read-only guardrails, powered by Gemini 2.5 Flash.

Full architecture and roadmap in the project deck (not included in this repo).
