#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/alert-bot"
REPO_URL="${REPO_URL:-https://github.com/shwlsdn2555/bitcoin-trading-bot.git}"
APP_USER="${APP_USER:-alertbot}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root."
  exit 1
fi

apt-get update
apt-get install -y git python3 python3-venv python3-pip ca-certificates

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env. Edit DISCORD_WEBHOOK_URL before starting the bot."
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

cp "$APP_DIR/vultr-alert-bot.service" /etc/systemd/system/alert-bot.service
systemctl daemon-reload
systemctl enable alert-bot

echo "Bootstrap complete."
echo "Next:"
echo "1. nano $APP_DIR/.env"
echo "2. systemctl restart alert-bot"
echo "3. systemctl status alert-bot"
