# Quant Trading Systems

This repository is a long-term quant trading research workspace for two separate systems:

1. Crypto quant trading system for Bitcoin and major coins.
2. Stock quant trading system for US and Korean markets.

The current production-ready program is the crypto Discord alert bot. The stock system is planned as a separate research track and will be built step by step.

All live-facing code is **alert-only by default**. It does not accept exchange API keys and does not place orders automatically.

## Project Roadmap

Start here:

```text
PROJECT_ROADMAP.md       Full long-term roadmap for crypto and stock systems
CRYPTO_SYSTEM_PLAN.md    Crypto strategy plan, universe, and research order
STOCK_SYSTEM_PLAN.md     US/Korea stock strategy plan and build order
DAILY_UPDATE_LOG.md      Daily manual/automatic progress journal
RESULTS_SUMMARY.md       Current validated research results
VULTR_OPERATIONS.md      Server setup, bot service, and daily update workflow
```

## Current Live Strategy

The current crypto live candidate is a multi-coin 4H swing portfolio strategy.

- Symbols: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT
- Timeframe: 4h
- Signal: Donchian 10 breakout
- Trend filter: EMA50 / EMA200
- Strength filter: ADX > 20
- Stop loss: ATR x 2
- Target: ATR x 4
- Maximum holding period: 24 four-hour candles, about 4 days

Backtest reference from 2023-04-28 to 2026-04-28:

- Monthly compound return: about 6.0%
- Total return: about 714%
- Max drawdown: about -23.0%
- Worst month: about -10.5%
- Trades: 357
- Profit factor: about 1.48

These are historical research results, not guaranteed future returns.

## Alert Contents

Discord alerts include:

- Symbol
- Long or short direction
- Entry zone
- Stop-loss level
- Target level
- Maximum holding period
- ADX and ATR context
- Suggested risk level
- Stable and aggressive sizing references
- Portfolio exposure limits

Signal outcomes are tracked in:

```text
logs/swing_alert_results.csv
```

## Code Files

```text
swing_portfolio_alert_bot.py   Main 4H portfolio monitoring and Discord alert bot
risk_research_backtest.py      Risk-focused portfolio backtesting
portfolio_swing_backtest.py    Portfolio-level strategy backtesting
backtest_alert_strategy.py     Original alert-strategy backtesting
optimize_strategy.py           Parameter optimization research
alert_only_futures_bot.py      Earlier alert-only futures bot
requirements.txt               Python dependencies
.env.example                   Example environment configuration
vultr-alert-bot.service        Example Linux systemd service
scripts/server_bootstrap.sh    Fresh Vultr server setup script
scripts/daily_server_update.sh Daily Vultr pull, backtest, and restart script
RESULTS_SUMMARY.md             Current research summary
QUANT_RESEARCH_CHARTER.md      Research rules and acceptance gates
AUTO_UPDATE_BACKLOG.md         Research backlog for automatic updates
GITHUB_SETUP.md                GitHub, laptop, and server workflow notes
```

## Development Tracks

Crypto track:
- Maintain the current Vultr Discord alert bot.
- Improve backtesting reports.
- Expand major coin universe only after validation.
- Promote live defaults only with backtest evidence.

Stock track:
- Start with US ETFs and indexes.
- Add Korean index/ETF logic separately.
- Use daily and weekly systems before any shorter timeframe.
- Compare every strategy against its benchmark.

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set your real Discord webhook URL.

## Server Update

On the Vultr server:

```bash
cd /opt/alert-bot
git pull
./venv/bin/pip install -r requirements.txt
systemctl restart alert-bot
systemctl status alert-bot
```

For a fresh server, follow `VULTR_OPERATIONS.md`.

## Safety Notes

- Do not commit `.env`.
- Do not commit Discord webhook URLs.
- Do not add exchange API keys to this alert-only version.
- Every live strategy change should be backed by a backtest first.
