import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import backtest_alert_strategy as bt
from portfolio_swing_backtest import DATA_DIR, symbol_key, write_csv


SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
SINCE = "2023-04-28"
UNTIL = "2026-04-28"
OUT_DIR = Path("./risk_research_results")


def load_symbol_frame(symbol):
    key = symbol_key(symbol)
    path = next(DATA_DIR.glob(f"{key}_4h_*.csv"))
    df = bt.load_csv(path)
    df["ema50"] = bt.ema(df["close"], 50)
    df["ema200"] = bt.ema(df["close"], 200)
    df["atr14"] = bt.atr(df, 14)
    df["adx14"] = bt.adx(df, 14)
    df["atr_pctile"] = df["atr14"].rolling(180).rank(pct=True)
    return df.dropna().reset_index(drop=True)


def btc_daily_regime():
    df = load_symbol_frame("BTC/USDT")
    dt = pd.to_datetime(df["ts"], unit="ms", utc=True)
    daily = df.assign(dt=dt).set_index("dt").resample("1D").agg({"close": "last"}).dropna()
    daily["ema50"] = bt.ema(daily["close"], 50)
    daily["ema200"] = bt.ema(daily["close"], 200)
    daily["regime"] = "NEUTRAL"
    daily.loc[daily["ema50"] > daily["ema200"], "regime"] = "BULL"
    daily.loc[daily["ema50"] < daily["ema200"], "regime"] = "BEAR"
    return [(int(idx.timestamp() * 1000), row["regime"]) for idx, row in daily.iterrows()]


def regime_at(regimes, ts):
    current = "NEUTRAL"
    for r_ts, value in regimes:
        if r_ts <= ts:
            current = value
        else:
            break
    return current


def simulate_trade(df, i, symbol, side, stop_mult, target_mult, max_hold_bars):
    entry_i = i + 1
    if entry_i >= len(df):
        return None, i
    entry = float(df.at[entry_i, "open"])
    atr = float(df.at[i, "atr14"])
    stop_dist = atr * stop_mult
    target_dist = atr * target_mult
    if stop_dist <= 0:
        return None, i

    if side == "LONG":
        stop = entry - stop_dist
        target = entry + target_dist
    else:
        stop = entry + stop_dist
        target = entry - target_dist

    exit_i = min(len(df) - 1, entry_i + max_hold_bars)
    exit_price = float(df.at[exit_i, "close"])
    reason = "TIME"
    for j in range(entry_i, min(len(df), entry_i + max_hold_bars + 1)):
        high = float(df.at[j, "high"])
        low = float(df.at[j, "low"])
        if side == "LONG":
            if low <= stop:
                exit_i = j
                exit_price = stop
                reason = "STOP"
                break
            if high >= target:
                exit_i = j
                exit_price = target
                reason = "TARGET"
                break
        else:
            if high >= stop:
                exit_i = j
                exit_price = stop
                reason = "STOP"
                break
            if low <= target:
                exit_i = j
                exit_price = target
                reason = "TARGET"
                break

    gross = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
    return {
        "symbol": symbol,
        "side": side,
        "entry_ts": int(df.at[entry_i, "ts"]),
        "exit_ts": int(df.at[exit_i, "ts"]),
        "entry": entry,
        "exit": exit_price,
        "stop": stop,
        "target": target,
        "stop_pct": abs(entry - stop) / entry,
        "net_return_on_notional": gross - 0.0008,
        "reason": reason,
        "bars_held": exit_i - entry_i + 1,
        "atr_pctile": float(df.at[i, "atr_pctile"]),
    }, exit_i


def generate_trades(symbols, lookback, adx_min, stop_mult, target_mult, max_hold_bars):
    start_ms = int(datetime.fromisoformat(SINCE).replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime.fromisoformat(UNTIL).replace(tzinfo=timezone.utc).timestamp() * 1000)
    all_trades = []
    for symbol in symbols:
        df = load_symbol_frame(symbol)
        high = df["high"].rolling(lookback).max().shift(1)
        low = df["low"].rolling(lookback).min().shift(1)
        long_mask = (df["close"] > high) & (df["ema50"] > df["ema200"]) & (df["adx14"] > adx_min)
        short_mask = (df["close"] < low) & (df["ema50"] < df["ema200"]) & (df["adx14"] > adx_min)
        i = 220
        while i < len(df) - max_hold_bars - 2:
            if int(df.at[i, "ts"]) < start_ms:
                i += 1
                continue
            if int(df.at[i, "ts"]) > end_ms:
                break
            side = "LONG" if bool(long_mask.iloc[i]) else ("SHORT" if bool(short_mask.iloc[i]) else None)
            if side:
                trade, exit_i = simulate_trade(df, i, symbol, side, stop_mult, target_mult, max_hold_bars)
                if trade and start_ms <= trade["entry_ts"] <= end_ms:
                    all_trades.append(trade)
                i = exit_i + 1
            else:
                i += 1
    return sorted(all_trades, key=lambda t: (t["entry_ts"], t["symbol"]))


def mdd_from_returns(returns):
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst


def portfolio(trades, cfg, regimes):
    equity = 1.0
    peak = 1.0
    worst_dd = 0.0
    open_positions = []
    closed = []
    month_pnl = {}
    paused_months = set()

    for trade in trades:
        entry_dt = datetime.fromtimestamp(trade["entry_ts"] / 1000, tz=timezone.utc)
        month = entry_dt.strftime("%Y-%m")
        open_positions = [p for p in open_positions if p["exit_ts"] > trade["entry_ts"]]
        if month in paused_months:
            continue

        regime = regime_at(regimes, trade["entry_ts"])
        regime_scale = 1.0
        if cfg["regime_filter"] == "strict":
            if trade["side"] == "LONG" and regime != "BULL":
                continue
            if trade["side"] == "SHORT" and regime != "BEAR":
                continue
        elif cfg["regime_filter"] == "risk_half":
            regime_scale = 0.5 if ((trade["side"] == "LONG" and regime != "BULL") or (trade["side"] == "SHORT" and regime != "BEAR")) else 1.0
        else:
            regime_scale = 1.0

        same_side = sum(1 for p in open_positions if p["side"] == trade["side"])
        if same_side >= cfg["max_same_side"]:
            continue
        if len(open_positions) >= cfg["max_positions"]:
            continue

        vol_scale = 1.0
        if cfg["vol_filter"] == "skip_extreme" and trade["atr_pctile"] >= 0.95:
            continue
        if cfg["vol_filter"] in ["half_high", "skip_extreme"] and trade["atr_pctile"] >= 0.80:
            vol_scale = 0.5

        risk_pct = cfg["risk_pct"] * regime_scale * vol_scale
        if month_pnl.get(month, 0.0) <= cfg["monthly_reduce_at"]:
            risk_pct *= 0.5
        if month_pnl.get(month, 0.0) <= cfg["monthly_stop_at"]:
            paused_months.add(month)
            continue

        current_exposure = sum(p["position_fraction"] for p in open_positions)
        position_fraction = min(cfg["max_position_fraction"], risk_pct / max(trade["stop_pct"], 0.001))
        if current_exposure + position_fraction > cfg["max_total_exposure"]:
            position_fraction = cfg["max_total_exposure"] - current_exposure
        if position_fraction <= 0:
            continue

        equity_return = trade["net_return_on_notional"] * position_fraction
        equity *= 1 + equity_return
        month_pnl[month] = month_pnl.get(month, 0.0) + equity_return
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity / peak - 1)

        row = dict(trade)
        row["position_fraction"] = position_fraction
        row["equity_return"] = equity_return
        row["equity_after"] = equity
        row["regime"] = regime
        row["entry_time_utc"] = entry_dt.isoformat()
        row["exit_time_utc"] = datetime.fromtimestamp(trade["exit_ts"] / 1000, tz=timezone.utc).isoformat()
        closed.append(row)
        open_positions.append({"exit_ts": trade["exit_ts"], "position_fraction": position_fraction, "side": trade["side"]})

    returns = [r["equity_return"] for r in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    months = {}
    for row in closed:
        months.setdefault(row["entry_time_utc"][:7], []).append(row["equity_return"])
    month_returns = [math.prod([1 + r for r in rs]) - 1 for rs in months.values()]
    summary = dict(cfg)
    summary.update({
        "trades": len(closed),
        "total_return": equity - 1,
        "monthly_compound": equity ** (1 / 36) - 1 if equity > 0 else -1,
        "active_month_avg": sum(month_returns) / len(month_returns) if month_returns else 0,
        "month_win_rate": sum(1 for r in month_returns if r > 0) / len(month_returns) if month_returns else 0,
        "win_rate": len(wins) / len(returns) if returns else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "max_drawdown": worst_dd,
        "worst_month": min(month_returns) if month_returns else 0,
        "best_month": max(month_returns) if month_returns else 0,
    })
    return summary, closed


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    regimes = btc_daily_regime()
    base_trades = generate_trades(SYMBOLS, lookback=10, adx_min=20, stop_mult=2.0, target_mult=4.0, max_hold_bars=24)
    write_csv(base_trades, OUT_DIR / "base_signal_trades.csv")

    rows = []
    best = None
    best_closed = None
    for risk_pct in [0.015, 0.02, 0.025, 0.03]:
        for regime_filter in ["none", "risk_half", "strict"]:
            for vol_filter in ["none", "half_high", "skip_extreme"]:
                for max_same_side in [1, 2]:
                    for monthly_reduce_at, monthly_stop_at in [(999, -999), (-0.06, -0.10), (-0.08, -0.12)]:
                        cfg = {
                            "risk_pct": risk_pct,
                            "max_positions": 2,
                            "max_same_side": max_same_side,
                            "max_position_fraction": 1.5,
                            "max_total_exposure": 3.0,
                            "regime_filter": regime_filter,
                            "vol_filter": vol_filter,
                            "monthly_reduce_at": monthly_reduce_at,
                            "monthly_stop_at": monthly_stop_at,
                        }
                        summary, closed = portfolio(base_trades, cfg, regimes)
                        rows.append(summary)
                        dd_ok = summary["max_drawdown"] > -0.30
                        key = (dd_ok, summary["monthly_compound"], summary["profit_factor"] or 0, summary["max_drawdown"])
                        if best is None or key > best:
                            best = key
                            best_closed = closed

    rows = sorted(rows, key=lambda r: (r["max_drawdown"] > -0.30, r["monthly_compound"], r["profit_factor"] or 0), reverse=True)
    write_csv(rows, OUT_DIR / "risk_research_grid.csv")
    write_csv(best_closed, OUT_DIR / "best_risk_trades.csv")
    (OUT_DIR / "best_risk_summary.json").write_text(json.dumps(rows[0], indent=2), encoding="utf-8")
    print(json.dumps(rows[:20], indent=2))


if __name__ == "__main__":
    main()
