# GitHub Setup

Use this project as the shared source of truth between desktop, laptop, and server.

## What Goes Into Git

Commit:
- Bot source files
- Backtest and research scripts
- Documentation
- `.env.example`
- Service file template

Do not commit:
- `.env`
- Discord webhook URLs
- Downloaded market data
- Logs
- Generated backtest CSV outputs
- Virtual environments

These exclusions are handled by `.gitignore`.

## This Repository

This folder is already connected to:

```bash
https://github.com/shwlsdn2555/bitcoin-trading-bot.git
```

## Push From This PC

After local changes are ready:

```bash
git status
git add .
git commit -m "Update quant trading alert system"
git push
```

## Continue On Laptop

On the laptop:

```bash
git clone https://github.com/shwlsdn2555/bitcoin-trading-bot.git
cd bitcoin-trading-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then edit `.env` locally and add your Discord webhook. Never commit `.env`.

## Update Server Later

On the Vultr server, after the repo exists:

```bash
cd /opt/alert-bot
git pull
./venv/bin/pip install -r requirements.txt
systemctl restart alert-bot
systemctl status alert-bot
```
