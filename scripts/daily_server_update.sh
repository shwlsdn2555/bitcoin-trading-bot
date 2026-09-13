#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alert-bot}"
LOG_DIR="$APP_DIR/logs"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_FILE="$LOG_DIR/server_daily_update.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "[$STAMP] Starting daily server update"
  git pull --ff-only
  ./venv/bin/pip install -r requirements.txt

  if [ -f portfolio_swing_backtest.py ]; then
    echo "[$STAMP] Running crypto portfolio backtest"
    ./venv/bin/python portfolio_swing_backtest.py || echo "[$STAMP] portfolio_swing_backtest.py failed"
  fi

  if [ -f risk_research_backtest.py ]; then
    echo "[$STAMP] Running risk research backtest"
    ./venv/bin/python risk_research_backtest.py || echo "[$STAMP] risk_research_backtest.py failed"
  fi

  systemctl restart alert-bot
  systemctl is-active alert-bot
  echo "[$STAMP] Daily server update finished"
} >> "$LOG_FILE" 2>&1
