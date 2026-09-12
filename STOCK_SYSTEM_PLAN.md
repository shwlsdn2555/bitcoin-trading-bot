# Stock Quant System Plan

## Purpose

Build a separate quant system for US and Korean stock markets. The stock system should begin with indexes and ETFs, then expand to individual stocks only after the baseline is stable.

## First Principle

Stocks are not crypto. The system must account for market sessions, overnight gaps, dividends, splits, liquidity, and event risk. It should use daily and weekly data first.

## Initial US Universe

Index and asset ETFs:

- SPY
- QQQ
- IWM
- DIA
- GLD
- TLT

Later expansion:

- Sector ETFs.
- Top S&P 500 liquid stocks.
- Nasdaq 100 liquid stocks.

## Initial Korea Universe

Start with broad and liquid proxies:

- KOSPI 200 ETF.
- KOSDAQ 150 ETF.
- Large liquid stocks after data handling is stable.

Later expansion:

- Market-cap and liquidity-ranked KOSPI names.
- Separate KOSDAQ research track.
- Sector or theme baskets only after core benchmark strategies work.

## Strategy Menu

### Baseline

- Daily trend-following.
- Moving average regime filter.
- Relative strength ranking.
- Volatility-adjusted position sizing.
- Defensive asset or cash filter.

### Research Candidates

- 6-month and 12-month momentum.
- 200-day moving average risk-on/risk-off.
- Dual momentum across stocks, bonds, gold, and cash.
- Pullback entries inside confirmed uptrends.
- Breakout entries after volatility compression.
- Weekly confirmation filters.

## Stock-Specific Risk Controls

- Avoid single-stock positions around earnings until earnings data is reliable.
- Limit position size for high gap-risk assets.
- Require liquidity and volume filters.
- Separate US and Korea calendars.
- Include benchmark comparison in every report.

## Backtest Requirements

Each candidate must report:

- Benchmark return.
- Strategy return.
- Monthly compound return.
- Annualized return.
- Max drawdown.
- Worst month.
- Sharpe-like volatility measure when available.
- Trade count.
- Turnover.
- Win rate.
- Exposure percentage.

## Near-Term Build Order

1. Create a separate stock backtest module.
2. Add ETF/index data download flow.
3. Implement simple daily moving-average baseline.
4. Add dual momentum strategy.
5. Add US ETF report.
6. Add Korean ETF/index report.
7. Compare stock results with crypto results.
8. Decide whether stock alerts should use Discord, separate channel, or separate bot.
