# Vultr Operations Guide

This guide keeps the server workflow simple:

```text
GitHub = source of truth
Vultr = always-on bot and scheduled research server
Local PC or laptop = development through Codex
```

## Fresh Server Setup

Use Ubuntu 22.04 or 24.04.

Connect as root, then run:

```bash
apt-get update
apt-get install -y git
git clone https://github.com/shwlsdn2555/bitcoin-trading-bot.git /tmp/bitcoin-trading-bot
bash /tmp/bitcoin-trading-bot/scripts/server_bootstrap.sh
```

Edit the real environment file:

```bash
nano /opt/alert-bot/.env
```

Set:

```text
DISCORD_WEBHOOK_URL=your_real_discord_webhook
```

Start or restart the bot:

```bash
systemctl restart alert-bot
systemctl status alert-bot
```

Watch logs:

```bash
journalctl -u alert-bot -f
```

## Daily Server Update

The server update script is:

```text
scripts/daily_server_update.sh
```

It does this:

- Pulls the latest GitHub code when server Git authentication is available.
- Continues with the files currently on the server if GitHub pull fails.
- Installs updated Python requirements.
- Runs available crypto research backtests.
- Restarts the alert bot.
- Writes logs to `/opt/alert-bot/logs/server_daily_update.log`.

## Cron Setup

Open cron:

```bash
crontab -e
```

Add this line to run every day at 17:00 server time:

```cron
0 17 * * * /bin/bash /opt/alert-bot/scripts/daily_server_update.sh
```

If the server uses UTC and you want Korea time 17:00, use 08:00 UTC:

```cron
0 8 * * * /bin/bash /opt/alert-bot/scripts/daily_server_update.sh
```

## GitHub Push From Server

The daily server script pulls from GitHub by default. It does not push automatically yet.

Automatic push should be added only after SSH key authentication is configured safely. Do not put GitHub passwords or tokens in `.env`.

If GitHub authentication is not configured yet, upload changed files with WinSCP and keep the daily server script running. The script will skip or log failed GitHub pulls instead of stopping the whole update.

## Useful Commands

```bash
cd /opt/alert-bot
git pull
./venv/bin/pip install -r requirements.txt
systemctl restart alert-bot
systemctl status alert-bot
journalctl -u alert-bot -f
tail -f logs/server_daily_update.log
```
