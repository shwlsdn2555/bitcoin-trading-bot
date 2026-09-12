# Research Results Summary

This file records the current research conclusions without committing large CSV data files.

## Current Live Candidate

Strategy:
- Symbols: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT
- Timeframe: 4h
- Signal: Donchian 10 breakout
- Trend filter: EMA50 / EMA200
- Strength filter: ADX > 20
- Stop: ATR x 2
- Target: ATR x 4
- Max hold: 24 four-hour candles, about 4 days

Risk controls:
- Risk per trade: 3%
- Max open positions: 2
- Max same-side positions: 1
- Max position notional: 1.5x account equity
- Max total exposure: 3x account equity
- Monthly -6%: halve risk
- Monthly -10%: stop new alerts for the month

Backtest reference:
- Period: 2023-04-28 to 2026-04-28
- Monthly compound return: about 6.0%
- Total return: about 714%
- Max drawdown: about -23.0%
- Worst month: about -10.5%
- Month win rate: about 64.9%
- Trades: 357
- Profit factor: about 1.48

## Important Notes

- This is not a guarantee of future performance.
- The system is alert-only and should not contain exchange API keys.
- Auto-trading must not be added without a separate explicit decision.
- Large market data and generated result folders are intentionally excluded from Git.
