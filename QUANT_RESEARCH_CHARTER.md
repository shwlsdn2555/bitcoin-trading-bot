# Quant Research Charter

This project is a research-driven trading assistant. Its purpose is to help produce tested trading alerts, not financial guarantees.

## Current Objective

Build two related but separate quant trading systems:

1. Crypto: Bitcoin and major liquid coins.
2. Stocks: US market indexes/ETFs first, then Korean market indexes/ETFs, then selected stocks.

Both systems should:

- Sends Discord alerts with entry, stop, target, holding period, and risk sizing.
- Uses no automated order placement by default.
- Continuously improves through backtesting and result tracking.
- Keeps risk controls visible and strict.

## Primary Metrics

Every serious candidate must report:

- Monthly compound return.
- Total return.
- Max drawdown.
- Worst month.
- Best month.
- Profit factor.
- Win rate.
- Month win rate.
- Trade count.
- Long/short split.
- Symbol contribution.

Stock candidates must additionally report:

- Benchmark return.
- Annualized return.
- Turnover.
- Exposure percentage.
- Gap and event-risk notes when relevant.

## Live Default Philosophy

Live defaults should prefer durability over headline return.

Preferred crypto default target:
- Monthly return: 4% to 6%.
- Max drawdown: 20% to 30%.

Aggressive crypto target:
- Monthly return: 7% to 9%.
- Max drawdown may exceed 35%, so this should be opt-in only.

Preferred stock target:
- Beat the relevant benchmark after drawdown and turnover are considered.
- Avoid strategies that only work during one market regime.

## Research Sources

Use public, checkable ideas:

- Trend following and time-series momentum.
- Breakout systems.
- Volatility targeting.
- Portfolio risk parity and exposure caps.
- Drawdown controls.
- Regime filters.
- Walk-forward testing.

Do not claim access to private strategies from other users. If an idea comes from public research, cite or describe the public basis when useful.

## Safety Rules

- No exchange API keys in alert-only bots.
- No automated order placement unless explicitly requested.
- No live default change without backtest evidence.
- No strategy promotion based on less than 100 trades unless clearly labeled experimental.
- Keep previous working files unless replacing them with a verified version.
- Keep crypto and stock research results separate until both are independently validated.
