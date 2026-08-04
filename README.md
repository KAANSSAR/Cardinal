# Cardinal

[![CI](https://github.com/KAANSSAR/Cardinal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAANSSAR/Cardinal/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-249%20passing-brightgreen)](https://github.com/KAANSSAR/Cardinal/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Bloomberg-terminal-style, multi-lens equity analysis platform combining fundamental DCF valuation, quantitative signal analytics, algorithmic backtesting, and agentic AI interpretation — for any ticker across US, Indian, and European markets.

## Status — complete platform

| Layer | Status |
|---|---|
| Fundamental (DCF) | ✅ Live sliders, comps table, DCF/comps reconciliation, sanity-checked outliers |
| Quant overlay | ✅ Momentum, Sharpe, beta, vol surface, RSI, Bollinger, hysteresis-stable signal bias |
| Algo backtest | ✅ Momentum (Golden Cross) and mean reversion strategies |
| AI agents (Xavi / Iniesta / Busquets / Messi) | ✅ Full team, sidebar, Messi chat, hedging-aware synthesis |
| Ground Truth DB | ✅ Human-verified response cache, feedback loop, admin dashboard |
| Market overview | ✅ Live indices, gainers/losers, sector heatmap, header ticker tape |
| UI | ✅ Full Bloomberg-terminal redesign — 3 switchable themes, continuous-scroll dashboard |

## What's built

**Backend — 249 tests passing**

Core computation:
- `core/dcf.py` — DCF engine: CAPM cost of equity, WACC, FCF projection, Gordon Growth terminal value
- `core/comps.py` — comparable companies: peer median multiples, implied EV
- `core/quant.py` — quant analytics: momentum (20d/60d/252d), rolling Sharpe, beta (252d OLS regression), realised vol surface, RSI, Bollinger Bands, **hysteresis-based signal bias classifier** (weighted multi-factor scoring, prevents label flip on noise)
- `core/backtest.py` — momentum (Golden Cross) and mean reversion strategies
- `core/market_overview.py` — **[new]** live market indices (S&P 500/NIFTY 50/DAX), gainers & losers, sector heatmap (SPDR ETF proxies), header ticker tape — 60s cached

AI agents (Gemini 3.5 Flash, thinking disabled):
- `agents/xavi.py` — Fundamental Analyst. DCF + comps reconciliation (flags method divergence >50%), DCF sanity-check warnings (flags outliers >70% from market price), beta methodology cross-check against Iniesta's regression beta, bear-case inherits sanity warnings
- `agents/iniesta.py` — Quant Analyst. Inherits the programmatically-computed signal bias rather than re-deriving one from raw numbers; standardised vol-surface terminology
- `agents/busquets.py` — Strategy Reviewer. Backtest edge verdict, regime observations, refinements
- `agents/messi.py` — Portfolio Manager. Orchestrates the team, synthesises BUY/HOLD/SELL (temperature 0.1, cached to prevent verdict drift), **inherits source-agent hedging language rather than re-editorialising**, plus a follow-up chat endpoint with full memo + live news context
- `agents/cache.py` — in-memory TTL cache (1hr), agent+ticker+params keyed
- `agents/news.py` — Tavily news context, graceful degradation
- `agents/gemini_client.py` — retry logic (exponential backoff) for transient 429/503 errors

Ground Truth DB — **[new]**:
- `db/ground_truth.py` — SQLite-backed verified-response store. Lookup order is GT DB → memory cache → Gemini. 3 positive feedback signals auto-verifies an entry for instant future retrieval. Tracks response times and call sources for the admin dashboard.

API — `api/main.py`, 20 endpoints:
- Fundamental/Quant/Backtest/Comps/Search — unchanged core endpoints, now with live currency conversion (`get_usd_rate`) and partial-data handling for incomplete tickers
- `POST /agent/{xavi,iniesta,busquets,messi}`, `POST /agent/messi/chat` — full agent team
- `POST /feedback`, `GET /admin/metrics`, `GET /admin/ground-truth`, `DELETE /admin/ground-truth/{id}` — GT DB + admin
- `GET /market/indices`, `GET /market/movers`, `GET /market/sectors`, `GET /market/ticker-tape` — **[new]** live market overview data

**Frontend — Vite + React 19 + TypeScript + Tailwind v4**

Full Bloomberg-terminal redesign — dark, dense, monospace-first:
- **Theme system** (`lib/ThemeContext.tsx`) — three switchable themes (Amber/Cyan/Green), runtime CSS-variable-driven, persisted to `localStorage`
- **Header** (`components/Header.tsx`) — live NYSE-hours clock, markets-open indicator, theme switcher, self-measures its height via `ResizeObserver` so other sticky elements can position against it precisely
- **Ticker tape** (`components/TickerTape.tsx`) — scrolling marquee, refetches on the same 60s cadence as its backend cache
- **Sparkline** (`components/Sparkline.tsx`) — reusable inline SVG line+area chart, no charting library, used across indices/movers
- **Homepage** — hero search, live market indices row, gainers & losers, sector heatmap (all wired to real data, not mocked)
- **Ticker dashboard** (`pages/TickerPage.tsx`) — converted from tabs to one continuous scroll page; Fundamental/Quant/Backtest are anchor-linked sections with real scroll-spy (`IntersectionObserver` + bottom-of-page override for the last section), sticky company header + nav row, back button using browser history
- **AI Sidebar** — unchanged functionality, fully reskinned: agent tabs, per-agent empty states, typing-dot loading animation, collapsible "thinking cloud" data snapshot, 👍/👎 feedback bar wired to the GT DB, Messi chat with click-to-edit sent messages
- **Admin Dashboard** (`pages/AdminDashboard.tsx`) — **[new]** platform KPIs, agent performance chart, GT DB browser (filter/search/verify/delete), activity feed, full API reference — same terminal theme, live-reactive Recharts colors
- Recharts retained only for the two genuinely interactive charts (Backtest P&L, Admin bar chart); everything else is hand-built SVG

## Project Structure

```
Cardinal/
├── src/cardinal/
│   ├── core/
│   │   ├── dcf.py
│   │   ├── comps.py
│   │   ├── quant.py                 # + signal bias hysteresis classifier
│   │   ├── backtest.py
│   │   └── market_overview.py       # [new] indices/movers/sectors/tape
│   ├── agents/
│   │   ├── gemini_client.py         # + retry logic
│   │   ├── xavi.py                  # + DCF sanity check, comps reconciliation
│   │   ├── iniesta.py               # + inherits computed signal bias
│   │   ├── busquets.py
│   │   ├── messi.py                 # + hedging inheritance, chat endpoint
│   │   ├── cache.py
│   │   └── news.py
│   ├── db/                          # [new] Ground Truth DB
│   │   └── ground_truth.py
│   ├── data/
│   │   ├── market_data.py           # + live currency conversion
│   │   ├── fmp_client.py
│   │   └── utils.py
│   ├── api/
│   │   ├── main.py                  # 20 endpoints
│   │   └── models.py
│   └── config.py
├── frontend/src/
│   ├── components/
│   │   ├── Header.tsx               # [new] self-measuring sticky header
│   │   ├── TickerTape.tsx           # [new] marquee
│   │   ├── Sparkline.tsx            # [new] inline SVG charts
│   │   ├── MarketIndices.tsx        # [new]
│   │   ├── GainersLosers.tsx        # [new]
│   │   ├── SectorHeatmap.tsx        # [new]
│   │   ├── Layout.tsx
│   │   ├── TickerSearch.tsx         # + hideButton mode for compact nav
│   │   ├── AssumptionsPanel.tsx
│   │   ├── DCFOutputCard.tsx
│   │   ├── CompsTable.tsx
│   │   ├── QuantDashboard.tsx
│   │   ├── BacktestView.tsx         # theme-reactive Recharts
│   │   └── AISidebar.tsx
│   ├── pages/
│   │   ├── Home.tsx                 # live market widgets
│   │   ├── TickerPage.tsx           # continuous scroll + scroll-spy
│   │   └── AdminDashboard.tsx       # [new]
│   └── lib/
│       ├── ThemeContext.tsx         # [new]
│       ├── api.ts
│       └── useDebounce.ts
├── tests/                           # 249 tests across 13 files
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
pytest tests/ -v        # 249 passing
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
# http://localhost:5173/admin — admin dashboard
```

**Docker:**
```bash
docker compose up
```

## Agent architecture

Four specialist agents named after the Barça midfield — each reads Cardinal's computed data as a frozen, read-only snapshot:

| Agent | Lens | Persona | Output |
|---|---|---|---|
| **Xavi** | Fundamental | IB Analyst | Valuation verdict reconciling DCF vs comps, bull/bear case, key risks, sanity-checked outliers |
| **Iniesta** | Quant | Desk Quant | Directional bias (hysteresis-stable), momentum analysis, vol regime, timing call |
| **Busquets** | Backtest | Strategy Reviewer | Strategy verdict, regime observations, refinements, risk flags |
| **Messi** | Synthesis | Portfolio Manager | BUY/HOLD/SELL verdict, inherits team's hedging language, follow-up chat |

**Data-quality guardrails, hardened over several rounds of live bug reports:**
- DCF outputs that diverge from both market price and comps-implied value by >70% trigger a `DCF_SANITY_WARNING` — surfaced in Key Risks, and the Bear Case can no longer present the flagged figure as a credible live scenario without an explicit outlier caveat
- Comps-implied price-per-share is computed and reconciled against the DCF figure whenever both exist — Xavi and Messi must present both, not just the more dramatic one
- Vendor beta (used in WACC) is cross-checked against Iniesta's independently-computed 252-day regression beta; a >10% gap triggers a `BETA_METHODOLOGY_NOTE` with the recomputed DCF fair value under both betas shown side by side
- Nominal vs. present-value FCF are both shown explicitly, so a mathematically-expected PV decline (when WACC > growth rate) isn't misread as a bearish cash flow signal
- Iniesta's Signal Bias is computed programmatically with weighted multi-factor scoring (not a single hard threshold), preventing the label from oscillating on noise-level input changes
- Messi's synthesis temperature is 0.1 and the verdict is cached per unique input combination, so re-running on unchanged data returns the same call
- Messi must inherit — not re-derive — any hedging language used by Busquets or Iniesta (e.g. "statistically unreliable due to low trade count" cannot be reframed as a confident signal)

**Orchestration:** `POST /agent/messi` runs Xavi → Iniesta → Busquets sequentially then synthesises. Each memo checks the Ground Truth DB first, then the in-memory cache, before calling Gemini — a fully-cached re-run drops from ~18s to under 1s.

## Ground Truth DB

Every agent call is logged with its response time and source (`gemini` / `cache` / `gt_db`). Users can vote 👍/👎 on any memo from the AI sidebar; 3 positive votes on a given ticker+agent+params combination auto-verifies it, after which it's served instantly from SQLite instead of re-calling Gemini. The `/admin` dashboard exposes the full GT DB (filter, search, expand memo, delete), platform-wide metrics, agent performance charts, an activity feed, and a live API reference.

## Why this exists

Bloomberg Terminal costs $24,000/year. No open tool combines DCF valuation, quant signal analytics, and algorithmic backtesting in a single interface with global market coverage — let alone a self-improving, human-verified AI interpretation layer on top. Cardinal closes that gap: production-grade architecture, CI/CD, a data-quality-hardened agent layer, and a genuine Bloomberg-terminal UI, built end to end.