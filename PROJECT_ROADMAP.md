# Quant Trading Project Roadmap

This repository is the shared source of truth for two long-term quant trading systems:

1. Crypto quant trading system.
2. US and Korea stock quant trading system.

Both systems must be research-first, backtest-driven, and alert-only by default. Live trading automation should be added only after a separate explicit decision.

## 1. Crypto Quant System

Scope:
- Bitcoin and a small set of highly liquid major coins.
- Initial universe: BTC, ETH, SOL, BNB, XRP.
- Later expansion candidates: ADA, DOGE, AVAX, LINK, LTC, BCH, NEAR, SUI.
- Primary market: crypto futures, but the default system sends alerts only.

Primary style:
- Multi-day swing trading.
- 4H and 1D timeframes first.
- Avoid short-term scalping.
- Prefer trend-following, breakout, and volatility-adjusted position sizing.

Core strategy families:
- Donchian breakout with EMA trend filter.
- Time-series momentum.
- ATR stop and target system.
- Trend-strength filter using ADX.
- Portfolio exposure caps.
- Monthly drawdown throttling.
- Later: regime filters, correlation filters, trailing exits, and symbol rotation.

Current baseline:
- 4H Donchian 10 breakout.
- EMA50 / EMA200 trend filter.
- ADX > 20.
- Stop ATR x 2.
- Target ATR x 4.
- Max hold 24 four-hour candles.
- Risk 3% per signal.
- Max 2 open positions.
- Max 1 same-side position.
- Max 1.5x notional per position.
- Max 3x total exposure.
- Reduce risk after monthly -6%.
- Stop new alerts after monthly -10%.

Current research reference:
- Backtest period: 2023-04-28 to 2026-04-28.
- Monthly compound return: about 6.0%.
- Max drawdown: about -23.0%.

## 2. Stock Quant System

Scope:
- US market first: S&P 500 / Nasdaq exposure through ETFs before individual stocks.
- Korea market next: KOSPI / KOSDAQ exposure through index ETFs or liquid large caps.
- Later: selected individual stocks only after benchmark ETF logic is stable.

Initial universe:
- US ETFs: SPY, QQQ, IWM, DIA, GLD, TLT.
- Korea index proxies: KOSPI 200 ETF, KOSDAQ 150 ETF, and liquid large-cap candidates.

Primary style:
- Daily and weekly swing/position trading.
- Avoid intraday trading at first.
- Account for market sessions, overnight gaps, dividends, splits, and earnings risk.

Core strategy families:
- Trend-following using moving average filters.
- Dual momentum: absolute momentum plus relative strength.
- Volatility targeting.
- Breakout or pullback entries in confirmed trends.
- Defensive asset rotation.
- Cash or bond allocation during weak regimes.

Required stock-specific controls:
- Gap risk measurement.
- Earnings and event avoidance for single stocks.
- Liquidity filters.
- Benchmark-relative performance.
- Separate US and Korea market calendars.

## Long-Term Development Phases

### Phase 1: Foundation

- Keep the current crypto alert bot stable.
- Separate project documentation for crypto and stocks.
- Add daily update logs.
- Standardize backtest result reporting.
- Make GitHub easy to read from any PC or laptop.

### Phase 2: Crypto Research Expansion

- Improve portfolio reports.
- Expand liquid coin universe.
- Compare trend, breakout, trailing stop, and regime filter variants.
- Keep the live default conservative unless a new variant improves both return and drawdown.

### Phase 3: Stock Research Foundation

- Build a separate stock data and backtest module.
- Start with ETFs and indexes.
- Add US stock logic first, then Korean stock logic.
- Validate daily/weekly systems over multiple market regimes.

### Phase 4: Unified Research Dashboard

- Summarize crypto and stock candidates in comparable metrics.
- Track live alerts versus backtest expectations.
- Add monthly review reports.
- Identify when live behavior deviates from historical assumptions.

### Phase 5: Deployment Discipline

- Keep Vultr running only alert-only production code.
- Keep research scripts in GitHub.
- Deploy live changes only after backtest evidence is added to the repository.
- Maintain rollback notes for every live strategy change.

## Daily Update Rule

Every automatic update should:

- Read this roadmap first.
- Read `QUANT_RESEARCH_CHARTER.md`.
- Read `AUTO_UPDATE_BACKLOG.md`.
- Choose one bounded task.
- Avoid live trading automation.
- Run feasible checks or backtests.
- Update `DAILY_UPDATE_LOG.md`.
- Leave GitHub-visible notes about changed files, results, and next steps.
