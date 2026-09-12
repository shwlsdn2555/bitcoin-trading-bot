# Quant Trading System Auto-Update Backlog

Goal: build two verified quant trading research and alert systems:

1. Crypto futures alert system for Bitcoin and major coins.
2. US/Korea stock quant system for indexes, ETFs, and later selected stocks.

Current live direction:
- Alert-only, no exchange API keys, no automated orders.
- Multi-coin 4H swing strategy.
- Researched baseline: BTC, ETH, SOL, BNB, XRP; Donchian 10 breakout; EMA50/EMA200 trend filter; ADX > 20; stop ATR x 2; target ATR x 4; max hold 24 four-hour candles.
- Current preferred risk profile: risk 3% per trade, max 2 open positions, max 1 same-side position, max 1.5x notional per position, max 3x total exposure, halve risk after monthly -6%, stop new alerts after monthly -10%.
- Backtest reference: monthly compound about 6.0%, max drawdown about -23.0% over 2023-04-28 to 2026-04-28.

## Operating Principles

1. Do not add automated order placement unless explicitly requested later.
2. Prefer robust, explainable rules over fragile curve-fitted parameters.
3. Every strategy change must be backed by a backtest before being proposed for live alerts.
4. Never optimize only for monthly return. Always report max drawdown, worst month, profit factor, trade count, month win rate, and year-by-year stability.
5. Treat monthly 8% as an aggressive research target, not a default live target, unless drawdown remains acceptable.
6. Use public, checkable ideas only. Do not claim access to private systems built by other users.
7. Keep live defaults conservative unless a new configuration improves return and drawdown together.

## Acceptance Gates

A strategy can be considered for live alert defaults only if it meets most of these:

- Minimum 100 trades over a 3-year backtest, unless it is explicitly a low-frequency satellite strategy.
- Profit factor above 1.30.
- Monthly compound return above 4.0% for balanced mode, or above 7.0% for aggressive mode.
- Max drawdown under 30% for balanced mode, or under 45% for aggressive mode.
- Worst month better than -15% for balanced mode.
- Positive or at least non-catastrophic performance across multiple calendar years.
- No obvious single-symbol dependency.

## Research Queue

### Priority 1: Portfolio Risk Improvement

- Add monthly and quarterly performance reports to portfolio backtests.
- Add equity curve CSV output.
- Add rolling 3-month drawdown and rolling 6-month return analysis.
- Compare max same-side position limit 1 vs 2 across multiple symbol sets.
- Compare monthly loss controls: reduce at -4/-6/-8%, stop at -8/-10/-12%.

### Priority 2: Symbol Universe Expansion

- Test additional liquid futures symbols: ADA, DOGE, AVAX, LINK, LTC, BCH, NEAR, SUI.
- Exclude symbols with too little history or unstable listing periods.
- Rank symbols by standalone PF, MDD, trade count, and contribution to portfolio diversification.
- Test top 5, top 8, top 10 symbol portfolios.

### Priority 3: Trend-Following Variants

- Donchian breakout lookbacks: 10, 20, 40, 60.
- EMA filters: EMA20/EMA100, EMA50/EMA200, close above/below EMA200.
- ADX thresholds: 15, 20, 25, 30.
- ATR stop/target pairs: 1.5/3, 2/3, 2/4, 2.5/5.
- Time exits: 3 days, 4 days, 6 days, 10 days.

### Priority 4: Trailing Exit Research

- After 1R profit, move stop to breakeven.
- After 2R profit, trail with EMA20 or ATR channel.
- Partial exit at 2R and trail the rest.
- Compare fixed target vs trailing target.

### Priority 5: Regime and Correlation Filters

- BTC daily bull/bear regime filter.
- Crypto market breadth filter using number of symbols above EMA200.
- High-volatility risk reduction using ATR percentile.
- Correlation cluster exposure limits.

### Priority 6: Stock Market Foundation

- Design a stock-compatible strategy module using daily data first.
- Start with ETFs before individual stocks: SPY, QQQ, IWM, GLD, TLT.
- Add stock-specific rules for gaps, earnings dates, market sessions, and overnight risk.
- Keep stock research separate from crypto futures until both are independently validated.

### Priority 7: Korea Stock Market Foundation

- Identify reliable KOSPI/KOSDAQ index or ETF data sources.
- Start with KOSPI 200 and KOSDAQ 150 style exposure.
- Add liquidity and gap filters before testing individual stocks.
- Build reports that compare strategy returns with the relevant Korean benchmark.

### Priority 8: GitHub Progress Hygiene

- Keep `DAILY_UPDATE_LOG.md` updated after every meaningful change.
- Keep `RESULTS_SUMMARY.md` focused on validated results only.
- Keep `PROJECT_ROADMAP.md` as the high-level direction.
- Keep code filenames descriptive enough that their purpose is obvious from GitHub.

## Next Automatic Task

Start with Priority 1. Improve the crypto research reports so every later experiment is easier to judge. Then begin Priority 6 with a separate stock backtest foundation.
