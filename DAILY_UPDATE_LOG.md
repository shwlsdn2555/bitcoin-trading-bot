# Daily Update Log

This file is the GitHub-visible progress journal for the long-term quant trading project.

Every manual or automatic update should add a new entry at the top.

## 2026-09-13

Focus:
- Report current automation progress.
- Make the Vultr daily update script safer for the current WinSCP-based deployment path.

Changed:
- Updated `scripts/daily_server_update.sh` so GitHub pull failure does not stop the whole daily job.
- Updated `VULTR_OPERATIONS.md` to document the WinSCP fallback and GitHub-authentication limitation.

Current status:
- Vultr bot is running under `alert-bot.service`.
- Codex daily automation is active for 17:00 local scheduled research.
- GitHub remains the source of truth, but Vultr Git authentication is not yet reliable.
- WinSCP upload is the current practical server update method.

Next:
- Add the cron entry on Vultr for `scripts/daily_server_update.sh`.
- Later, fix GitHub authentication from Vultr using a cleaner SSH or token setup outside noVNC.

## 2026-09-13 Earlier

Focus:
- Continue the GitHub + Vultr operating model.
- Add repeatable server setup and daily server update files.

Changed:
- Added `scripts/server_bootstrap.sh`.
- Added `scripts/daily_server_update.sh`.
- Added `VULTR_OPERATIONS.md`.
- Updated `README.md` to point to the new Vultr workflow.

Current status:
- GitHub remains the source of truth.
- Vultr is the preferred always-on runtime for the alert bot and scheduled jobs.
- GitHub Actions is intentionally deferred to reduce complexity.

Next:
- Configure a fresh or reactivated Vultr server from `VULTR_OPERATIONS.md`.
- Add safe GitHub SSH authentication later if automatic push from Vultr becomes necessary.

## 2026-09-12

Focus:
- Split the long-term project into two tracks: crypto quant system and US/Korea stock quant system.
- Make the repository easier to understand from GitHub.
- Prepare the daily automation to follow a clear roadmap.

Changed:
- Added `PROJECT_ROADMAP.md`.
- Added `CRYPTO_SYSTEM_PLAN.md`.
- Added `STOCK_SYSTEM_PLAN.md`.
- Added `DAILY_UPDATE_LOG.md`.
- Updated the automation scope to maintain both crypto and stock research tracks.

Current status:
- Crypto alert bot exists and is the current production-ready alert-only track.
- Stock system is planned but not implemented yet.
- Future automatic updates should choose one bounded task, run feasible tests or backtests, and record progress here.

Next:
- Improve crypto backtest reporting first.
- Then start the stock ETF/index backtest foundation.
