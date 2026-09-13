# Profitability Improvement Auto-Update Backlog

Goal: run a small, repeatable research loop that tries to improve the alert-only quant system over time.

The automation should not chase one lucky backtest. It should search for durable improvements, reject weak ideas quickly, and keep the live bot conservative unless evidence is strong.

## Current Baselines

### Live Baseline: Balanced Growth

- Universe: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT
- Timeframe: 4h
- Signal: Donchian 10 breakout
- Trend filter: EMA50 / EMA200
- Strength filter: ADX > 20
- Stop/target: ATR x 2 / ATR x 4
- Max hold: 24 four-hour bars
- Risk: 3% per trade
- Exposure: max 2 positions, max 1 same-side, max 1.5x per position, max 3x total
- Monthly controls: reduce at -6%, stop at -10%
- Reference result: monthly compound about 6.0%, MDD about -23.0%, worst month about -10.5%, month win rate about 64.9%, 357 trades, PF about 1.48

### Conservative Baseline: Stable Alternative

- Same signal and universe as the live baseline
- Volatility filter: skip extreme ATR percentile
- Risk: 2.5% per trade
- Monthly controls: reduce at -8%, stop at -12%
- Reference result: monthly compound about 4.40%, MDD about -19.85%, worst month about -12.18%, month win rate about 70.3%, 338 trades, PF about 1.46

## Daily Research Loop

Each daily automatic update should process one bounded task:

1. Select one hypothesis from the queue below.
2. State the expected benefit before editing code.
3. Make the smallest implementation needed to test the idea.
4. Run syntax checks and the relevant backtest.
5. Compare metrics against the live and stable baselines.
6. Mark the result as accepted, rejected, or needs-more-testing.
7. Update `DAILY_UPDATE_LOG.md` with the evidence.
8. Update `RESULTS_SUMMARY.md` only for validated accepted results.
9. Send one daily KakaoTalk summary with the result.

Do not start a second hypothesis in the same run unless the first one required no code change and finished quickly.

## Acceptance Rules

A change can be marked accepted only when it improves at least one important weakness without creating a larger new weakness.

Balanced mode acceptance:

- Monthly compound remains near or above 5.0%.
- Max drawdown stays below 30%.
- Worst month stays better than -15%.
- Profit factor stays above 1.35.
- Trade count stays above 100.
- No single symbol explains most of the improvement.

Stable mode acceptance:

- Monthly compound remains near or above 4.0%.
- Max drawdown improves versus the balanced baseline or stays below 22%.
- Worst month stays better than -14%.
- Month win rate stays near or above 65%.
- Profit factor stays above 1.35.

Aggressive mode acceptance:

- Monthly compound can target 7% to 9%.
- Max drawdown must be reported clearly and should stay below 45%.
- Aggressive mode must stay opt-in and must not replace the live default automatically.

Reject a change when:

- It only improves total return by increasing drawdown sharply.
- It reduces trade count below 100 without a clear satellite-strategy reason.
- It depends on one symbol, one year, or one unusually strong month.
- It makes logs, configuration, or live operation harder to understand.
- It requires exchange API keys or automated order placement.

## Priority Queue

### P1: Monthly Loss Defense

Hypothesis: the system can keep most upside while reducing weak-month damage.

Tasks:

- Compare monthly reduce levels: -4%, -6%, -8%, -10%.
- Compare monthly stop levels: -8%, -10%, -12%, -15%.
- Report return, MDD, worst month, month win rate, and trade count.
- Prefer rules that reduce worst month without killing monthly compound.

Decision target:

- Find one balanced setting and one stable setting worth documenting.

### P2: Symbol Contribution Pruning

Hypothesis: removing weak symbols can improve portfolio stability.

Tasks:

- Generate symbol-level PF, MDD, trade count, and contribution reports.
- Test portfolios that exclude the worst one or two symbols.
- Test top 3, top 4, and top 5 symbol sets by robust contribution.
- Check that removed symbols are not useful diversifiers during bad BTC periods.

Decision target:

- Keep the current 5-symbol universe unless pruning improves drawdown or PF without overfitting.

### P3: Volatility Regime Filter

Hypothesis: avoiding extreme volatility periods reduces drawdown and false breakouts.

Tasks:

- Compare no filter, skip top 5% ATR percentile, skip top 10%, and reduce risk in top 10%.
- Check whether volatility filters help both long and short trades.
- Compare against the stable alternative that already uses `skip_extreme`.

Decision target:

- Decide whether `BOT_VOL_FILTER=skip_extreme` should remain conservative-only or become live default.

### P4: Same-Side and Exposure Limits

Hypothesis: portfolio-level exposure caps can reduce correlated losses.

Tasks:

- Compare max same-side 1 vs 2.
- Compare max total exposure 2x, 3x, 4x, 5x.
- Compare max position fraction 1.0x, 1.5x, 2.0x.
- Report drawdown improvement per unit of return sacrificed.

Decision target:

- Preserve max same-side 1 unless evidence strongly supports wider exposure.

### P5: Exit Logic Improvements

Hypothesis: exits can improve PF and reduce reversals after open profit.

Tasks:

- Test breakeven stop after 1R.
- Test ATR trailing stop after 2R.
- Test EMA20 trailing stop after 2R.
- Test partial exit at 2R with trailing remainder.
- Compare fixed target vs trailing target.

Decision target:

- Accept only if PF or drawdown improves without major trade-count collapse.

### P6: Breakout and Trend Variants

Hypothesis: current Donchian 10 / EMA50-200 / ADX20 setup may not be the most robust.

Tasks:

- Donchian lookbacks: 10, 20, 40, 60.
- EMA filters: EMA20/100, EMA50/200, close above/below EMA200.
- ADX thresholds: 15, 20, 25, 30.
- ATR stop/target pairs: 1.5/3, 2/3, 2/4, 2.5/5.
- Time exits: 18, 24, 36, 60 four-hour bars.

Decision target:

- Avoid changing the live signal unless the improvement is broad across metrics.

### P7: Symbol Universe Expansion

Hypothesis: adding liquid coins can improve diversification and opportunity count.

Tasks:

- Test ADA, DOGE, AVAX, LINK, LTC, BCH, NEAR, SUI.
- Exclude symbols with short or unstable history.
- Rank each by standalone quality and portfolio contribution.
- Test top 5, top 8, and top 10 portfolios.

Decision target:

- Add symbols only when they improve stability, not just trade count.

### P8: Walk-Forward and Out-of-Sample Checks

Hypothesis: accepted settings should survive simple time splits.

Tasks:

- Split 2023, 2024, 2025, and 2026-to-date.
- Test rolling train/test windows when enough data exists.
- Compare chosen candidates against naive parameter neighbors.
- Flag any result that only works in one year.

Decision target:

- Promote only candidates that are not obviously one-period artifacts.

### P9: Stock System Foundation

Hypothesis: a separate stock ETF system can diversify away from crypto-only risk.

Tasks:

- Build daily-data ETF backtest foundation for SPY, QQQ, IWM, GLD, TLT.
- Add benchmark comparison.
- Track turnover, exposure percentage, drawdown, and annualized return.
- Keep this separate from crypto futures research.

Decision target:

- Produce first stock baseline before individual-stock research.

### P10: Korea Stock Foundation

Hypothesis: Korean ETF/index research can become a separate regional strategy.

Tasks:

- Identify reliable KOSPI 200 and KOSDAQ 150 data sources.
- Build a basic daily trend-following benchmark comparison.
- Add liquidity and gap-risk notes before individual-stock tests.

Decision target:

- Do not mix Korean stock assumptions into the crypto or US ETF system.

## Live Default Protection

The automation may research any queue item, but it must not silently change live defaults.

Allowed automatically:

- Add research scripts.
- Add reports.
- Add config options disabled by default.
- Document accepted candidates.
- Improve logging, health checks, and notifications.

Requires explicit user approval:

- Change `.env.example` live default risk above 3%.
- Change live symbols.
- Change live stop/target or signal defaults.
- Add exchange API keys.
- Add automated order placement.

## Next Automatic Task

Start with P1 monthly loss defense unless it is already complete for the current baseline. If P1 is complete, continue to P2 symbol contribution pruning.
