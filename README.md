# Futures Swing Portfolio Alert Bot

This is an alert-only bot. It does not accept exchange API keys and does not place orders.

The current default strategy is the researched multi-coin 4H swing portfolio model:

- Symbols: BTC, ETH, SOL, BNB, XRP
- Signal: 4H Donchian 10 breakout
- Trend filter: EMA50 / EMA200
- Strength filter: ADX > 20
- Stop: ATR x 2
- Target: ATR x 4
- Max hold: 24 four-hour candles, about 4 days
- Default risk: 3%
- Max positions: 2
- Max same-side positions: 1
- Monthly risk reduction: halve risk after -6%, stop new alerts after -10%

## Local quick start

1. Create a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set `DISCORD_WEBHOOK_URL`.
4. Test Discord:

```powershell
python swing_portfolio_alert_bot.py --test-discord
```

5. Check the strategy once:

```powershell
python swing_portfolio_alert_bot.py --once
```

6. Run continuously:

```powershell
python swing_portfolio_alert_bot.py
```

## Useful commands

Run one scan without keeping the process open:

```powershell
python swing_portfolio_alert_bot.py --once
```

## Alert fields

Each signal alert includes symbol, direction, entry zone, ATR-based stop, ATR-based target, max hold period, ADX, default risk, stable-mode notional, aggressive-mode notional, and portfolio exposure limits.

## Added quant filters

The live bot now checks:

- ADX trend strength
- ATR-based dynamic TP/SL levels
- Max open positions
- Max same-side positions
- Max total exposure
- Monthly risk reduction
- Monthly new-alert stop

It also tracks open alerts after they are sent. If target, stop, or time expiry occurs, it writes the result to:

```text
logs/swing_alert_results.csv
```

## Next upgrade path

1. Stabilize alert-only operation.
2. Add backtesting and walk-forward reports.
3. Track every alert result automatically.
4. Add Vultr monitoring and restart behavior.
5. Only after enough evidence, consider a separate auto-trading module.

## Backtest

Run the portfolio research backtest:

```powershell
python risk_research_backtest.py
```

Run the broader portfolio parameter grid:

```powershell
python portfolio_swing_backtest.py
```
