# Daily Update Log

This file is the GitHub-visible progress journal for the long-term quant trading project.

Every manual or automatic update should add a new entry at the top.

## 2026-09-13

Focus:
- Prepare KakaoTalk start/end notifications for daily quant updates.

Changed:
- Added `scripts/kakao_notify.py`.
- Added `KAKAO_NOTIFY_SETUP.md`.
- Added Kakao notification environment placeholders to `.env.example`.
- Updated `README.md` to list the Kakao setup and helper script.

Current status:
- Kakao notification code is ready but disabled until Kakao Developers access token setup is complete.
- Codex automation can report usage before work, but Kakao delivery requires a configured Kakao token.

Next:
- Configure Kakao Developers `talk_message` permission and access token.
- Then enable `KAKAO_NOTIFY_ENABLED=true` in `.env` and test `scripts/kakao_notify.py`.

## 2026-09-13 Earlier

Focus:
- Document the confirmed lower-drawdown crypto candidate from the improved risk research output.

Changed:
- Updated `RESULTS_SUMMARY.md` with a stable alternative candidate.
- Compared the current live candidate against the lower-drawdown candidate.
- Added live bot support for `BOT_VOL_FILTER=skip_extreme` so the stable candidate can be configured from `.env`.

Confirmed metrics:
- Current live candidate: monthly compound about 6.0%, MDD about -23.0%, 357 trades, profit factor about 1.48.
- Stable alternative: monthly compound about 4.40%, MDD about -19.85%, 338 trades, profit factor about 1.46.

Current status:
- The live default remains the balanced growth candidate.
- The stable alternative is now documented as a conservative mode candidate.

Next:
- Add a config switch or `.env` preset so the live bot can run either balanced growth mode or stable mode without manual parameter confusion.

## 2026-09-13 Earlier

Focus:
- Start Priority 1 from the research backlog: improve crypto portfolio reporting.

Changed:
- Added reusable research report helpers to `portfolio_swing_backtest.py`.
- Connected `portfolio_swing_backtest.py` to export best portfolio equity curve, monthly, quarterly, yearly, symbol, and rolling monthly reports.
- Connected `risk_research_backtest.py` to export the same report set for the best risk configuration.

Current status:
- The next crypto backtest run will produce GitHub-readable CSV reports under ignored result folders.
- Validated headline metrics in `RESULTS_SUMMARY.md` remain unchanged until the improved backtest is run.

Next:
- Run the improved backtests on Vultr, then summarize the new report files and update `RESULTS_SUMMARY.md` if the metrics are confirmed.

## 2026-09-13 Earlier

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
