# Futures Swing Portfolio Alert Bot

A Python-based crypto swing trading research and alert system designed to generate rule-based futures signals, backtest portfolio strategies, manage risk, and send Discord alerts.

> This project is currently an **alert-only system**.  
> It does not accept exchange API keys and does not place orders automatically.

## Project Overview

This project was created to research and automate a multi-asset crypto swing trading strategy.

The system monitors major crypto assets, applies trend and strength filters, calculates ATR-based risk levels, generates trading alerts, and tracks the outcome of previously generated signals.

The current default model is a multi-coin 4H swing portfolio strategy.

## Strategy Logic

### Markets

- BTC/USDT
- ETH/USDT
- SOL/USDT
- BNB/USDT
- XRP/USDT

### Entry Logic

The strategy uses:

- 4H Donchian Channel breakout
- EMA50 / EMA200 trend filter
- ADX trend-strength filter
- ATR-based volatility measurement

### Risk Management

- Stop Loss: ATR × 2
- Target: ATR × 4
- Maximum holding period: 24 × 4H candles
- Default risk per signal: 3%
- Maximum open positions: 2
- Maximum same-side positions: 1
- Monthly risk reduction after -6%
- Stop generating new alerts after -10% monthly drawdown

## Key Features

- Multi-asset market monitoring
- Rule-based signal generation
- Portfolio-level risk controls
- ATR-based dynamic stop-loss and take-profit levels
- ADX trend-strength filtering
- Position exposure limits
- Discord alert integration
- Signal result tracking
- Backtesting tools
- Parameter optimization
- Research utilities

## Alert System

Each signal alert contains:

- Symbol
- Long / Short direction
- Entry zone
- Stop-loss level
- Target level
- Maximum holding period
- ADX value
- Suggested risk level
- Stable-mode position size
- Aggressive-mode position size
- Portfolio exposure limits

The system also tracks previously generated alerts.

When a target, stop, or time expiration occurs, the result is recorded in:

```text
logs/swing_alert_results.csv
Project Structure
swing_portfolio_alert_bot.py
    Main portfolio monitoring and Discord alert bot.

risk_research_backtest.py
    Research and risk-focused backtesting.

portfolio_swing_backtest.py
    Portfolio-level strategy backtesting.

backtest_alert_strategy.py
    Backtesting utilities for the alert strategy.

optimize_strategy.py
    Strategy parameter optimization.

alert_only_futures_bot.py
    Futures alert generation logic.

requirements.txt
    Python dependencies.

.env.example
    Example environment configuration.

vultr-alert-bot.service
    Example Linux service configuration for server deployment.
Local Setup
1. Create a virtual environment
Create and activate a Python virtual environment.
2. Install dependencies
pip install -r requirements.txt