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
  if [ -d .git ]; then
    echo "[$STAMP] Pulling latest GitHub changes"
    if ! git pull --ff-only; then
      echo "[$STAMP] Git pull failed. Continuing with files currently on the server."
    fi
  else
    echo "[$STAMP] No .git directory found. Skipping GitHub pull."
  fi

  if [ -x ./venv/bin/pip ]; then
    ./venv/bin/pip install -r requirements.txt
  else
    echo "[$STAMP] Missing venv. Create it with: python3 -m venv venv"
  fi

  if [ -x ./venv/bin/python ] && [ -f portfolio_swing_backtest.py ]; then
    echo "[$STAMP] Running crypto portfolio backtest"
    ./venv/bin/python portfolio_swing_backtest.py || echo "[$STAMP] portfolio_swing_backtest.py failed"
  fi

  if [ -x ./venv/bin/python ] && [ -f risk_research_backtest.py ]; then
    echo "[$STAMP] Running risk research backtest"
    ./venv/bin/python risk_research_backtest.py || echo "[$STAMP] risk_research_backtest.py failed"
  fi

  if systemctl list-unit-files alert-bot.service >/dev/null 2>&1; then
    systemctl restart alert-bot
    systemctl is-active alert-bot
  else
    echo "[$STAMP] alert-bot.service is not installed."
  fi
  echo "[$STAMP] Daily server update finished"
} >> "$LOG_FILE" 2>&1
