# Crypto Quant System Plan

## Purpose

Build an alert-only crypto futures quant system for Bitcoin and major liquid coins. The system should identify multi-day swing opportunities, send Discord alerts, and improve through backtesting before any live default changes.

## Current Program

Main live bot:

```text
swing_portfolio_alert_bot.py
```

Research scripts:

```text
portfolio_swing_backtest.py
risk_research_backtest.py
optimize_strategy.py
backtest_alert_strategy.py
```

## Initial Market Universe

- BTC/USDT
- ETH/USDT
- SOL/USDT
- BNB/USDT
- XRP/USDT

Expansion candidates:

- ADA/USDT
- DOGE/USDT
- AVAX/USDT
- LINK/USDT
- LTC/USDT
- BCH/USDT
- NEAR/USDT
- SUI/USDT

## Strategy Menu

### Baseline

- 4H Donchian breakout.
- EMA50 / EMA200 trend filter.
- ADX trend-strength filter.
- ATR stop and target.
- Time-based exit.
- Portfolio-level exposure caps.

### Research Candidates

- Daily trend regime filter.
- Symbol strength ranking.
- ATR percentile volatility filter.
- Partial take profit plus trailing stop.
- Correlation-aware exposure limit.
- Weekly trend confirmation.

## Backtest Requirements

Each candidate must report:

- Period tested.
- Symbols used.
- Total return.
- Monthly compound return.
- Max drawdown.
- Worst month.
- Best month.
- Profit factor.
- Win rate.
- Month win rate.
- Trade count.
- Symbol contribution.

## Live Promotion Rule

A crypto strategy can replace the live default only if:

- It has at least 100 historical trades.
- It improves either return or drawdown without making the other meaningfully worse.
- It does not rely on a single coin.
- It keeps alert-only safety intact.
- The evidence is written to `RESULTS_SUMMARY.md`.

## Near-Term Build Order

1. Improve portfolio report output.
2. Add monthly, quarterly, and yearly result summaries.
3. Add equity curve CSV export.
4. Add rolling drawdown and rolling return analysis.
5. Expand symbol universe.
6. Test trailing exits.
7. Add regime filters.
8. Review whether the live default should change.
