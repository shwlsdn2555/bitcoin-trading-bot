#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alert-bot}"
LOG_DIR="$APP_DIR/logs"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_FILE="$LOG_DIR/server_daily_update.log"
RUN_LOG="$LOG_DIR/server_daily_update_${STAMP//[:]/-}.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

send_kakao() {
  local title="$1"
  local text="$2"

  if [ -x ./venv/bin/python ] && [ -f scripts/kakao_notify.py ]; then
    ./venv/bin/python scripts/kakao_notify.py --title "$title" --text "$text" >> "$LOG_FILE" 2>&1 || true
  fi
}

finish_update() {
  local status="$1"
  local finished_at
  local service_status
  local summary

  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  service_status="$(systemctl is-active alert-bot 2>/dev/null || echo unknown)"
  summary="$(tail -n 12 "$RUN_LOG" 2>/dev/null || true)"

  if [ "$status" -eq 0 ]; then
    send_kakao "Quant server update finished" "Status: success
Finished: $finished_at
Service: $service_status
Log: $LOG_FILE

Recent log:
$summary"
  else
    send_kakao "Quant server update failed" "Status: failed with exit code $status
Finished: $finished_at
Service: $service_status
Log: $LOG_FILE

Recent log:
$summary"
  fi
}

trap 'status=$?; finish_update "$status"; exit "$status"' EXIT

send_kakao "Quant server update starting" "Planned task: pull latest GitHub changes, install requirements, run crypto/risk backtests, restart alert-bot.
Started: $STAMP
Directory: $APP_DIR
Log: $LOG_FILE"

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

  if [ -x ./venv/bin/python ] && [ -f monthly_loss_defense_research.py ]; then
    echo "[$STAMP] Running monthly loss defense research"
    ./venv/bin/python monthly_loss_defense_research.py || echo "[$STAMP] monthly_loss_defense_research.py failed"
  fi

  if systemctl list-unit-files alert-bot.service >/dev/null 2>&1; then
    systemctl restart alert-bot
    systemctl is-active alert-bot
  else
    echo "[$STAMP] alert-bot.service is not installed."
  fi
  echo "[$STAMP] Daily server update finished"
} 2>&1 | tee -a "$LOG_FILE" "$RUN_LOG" >/dev/null
