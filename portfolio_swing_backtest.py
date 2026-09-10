import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import backtest_alert_strategy as bt


SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
OUT_DIR = Path("./portfolio_results")
DATA_DIR = Path("./portfolio_data")


@dataclass
class SignalTrade:
    symbol: str
    side: str
    entry_ts: int
    exit_ts: int
    entry: float
    exit: float
    stop: float
    target: float
    stop_pct: float
    net_return_on_notional: float
    reason: str
    bars_held: int


def symbol_key(symbol):
    return symbol.replace("/", "")


def prepare_4h(symbol, since, until):
    key = symbol_key(symbol)
    start_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(until).replace(tzinfo=timezone.utc)
    warmup_dt = start_dt - timedelta(days=150)
    path = DATA_DIR / f"{key}_4h_{warmup_dt.date()}_{end_dt.date()}.csv"
    df = bt.fetch_ohlcv_range(symbol, "4h", warmup_dt, end_dt, path)
    df["ema50"] = bt.ema(df["close"], 50)
    df["ema200"] = bt.ema(df["close"], 200)
    df["atr14"] = bt.atr(df, 14)
    df["adx14"] = bt.adx(df, 14)
    return df.dropna().reset_index(drop=True), int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


def simulate_trade(df, i, symbol, side, stop_mult, target_mult, max_hold_bars, fee_rate):
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
    net = gross - fee_rate * 2
    return SignalTrade(
        symbol=symbol,
        side=side,
        entry_ts=int(df.at[entry_i, "ts"]),
        exit_ts=int(df.at[exit_i, "ts"]),
        entry=entry,
        exit=exit_price,
        stop=stop,
        target=target,
        stop_pct=abs(entry - stop) / entry,
        net_return_on_notional=net,
        reason=reason,
        bars_held=exit_i - entry_i + 1,
    ), exit_i


def generate_symbol_trades(symbol, since, until, lookback, adx_min, stop_mult, target_mult, max_hold_bars, fee_rate):
    df, start_ms, end_ms = prepare_4h(symbol, since, until)
    high = df["high"].rolling(lookback).max().shift(1)
    low = df["low"].rolling(lookback).min().shift(1)
    long_mask = (df["close"] > high) & (df["ema50"] > df["ema200"]) & (df["adx14"] > adx_min)
    short_mask = (df["close"] < low) & (df["ema50"] < df["ema200"]) & (df["adx14"] > adx_min)

    trades = []
    i = 220
    while i < len(df) - max_hold_bars - 2:
        if int(df.at[i, "ts"]) < start_ms:
            i += 1
            continue
        if int(df.at[i, "ts"]) > end_ms:
            break
        side = "LONG" if bool(long_mask.iloc[i]) else ("SHORT" if bool(short_mask.iloc[i]) else None)
        if side:
            trade, exit_i = simulate_trade(df, i, symbol, side, stop_mult, target_mult, max_hold_bars, fee_rate)
            if trade and start_ms <= trade.entry_ts <= end_ms:
                trades.append(trade)
            i = exit_i + 1
        else:
            i += 1
    return trades


def generate_all_trades(symbols, since, until, cfg):
    all_trades = []
    for symbol in symbols:
        print(f"building trades for {symbol}")
        all_trades.extend(generate_symbol_trades(
            symbol,
            since,
            until,
            cfg["lookback"],
            cfg["adx_min"],
            cfg["stop_mult"],
            cfg["target_mult"],
            cfg["max_hold_bars"],
            cfg["fee_rate"],
        ))
    return sorted(all_trades, key=lambda t: (t.entry_ts, t.symbol))


def portfolio_backtest(trades, risk_pct, max_positions, max_position_fraction, max_total_exposure):
    equity = 1.0
    peak = 1.0
    worst_dd = 0.0
    open_positions = []
    closed_rows = []
    equity_points = []

    for trade in trades:
        open_positions = [p for p in open_positions if p["exit_ts"] > trade.entry_ts]
        current_exposure = sum(p["position_fraction"] for p in open_positions)
        if len(open_positions) >= max_positions or current_exposure >= max_total_exposure:
            continue

        position_fraction = min(max_position_fraction, risk_pct / max(trade.stop_pct, 0.001))
        if current_exposure + position_fraction > max_total_exposure:
            position_fraction = max_total_exposure - current_exposure
        if position_fraction <= 0:
            continue

        equity_return = trade.net_return_on_notional * position_fraction
        equity *= 1 + equity_return
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity / peak - 1)

        row = trade.__dict__.copy()
        row["position_fraction"] = position_fraction
        row["equity_return"] = equity_return
        row["equity_after"] = equity
        row["entry_time_utc"] = datetime.fromtimestamp(trade.entry_ts / 1000, tz=timezone.utc).isoformat()
        row["exit_time_utc"] = datetime.fromtimestamp(trade.exit_ts / 1000, tz=timezone.utc).isoformat()
        closed_rows.append(row)
        open_positions.append({"exit_ts": trade.exit_ts, "position_fraction": position_fraction})
        equity_points.append((trade.exit_ts, equity))

    returns = [r["equity_return"] for r in closed_rows]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    months = {}
    for row in closed_rows:
        month = row["entry_time_utc"][:7]
        months.setdefault(month, []).append(row["equity_return"])
    month_returns = [math.prod([1 + r for r in rs]) - 1 for rs in months.values()]
    summary = {
        "trades": len(closed_rows),
        "total_return": equity - 1,
        "monthly_compound": equity ** (1 / 36) - 1 if equity > 0 else -1,
        "active_month_avg": sum(month_returns) / len(month_returns) if month_returns else 0.0,
        "month_win_rate": sum(1 for r in month_returns if r > 0) / len(month_returns) if month_returns else 0.0,
        "win_rate": len(wins) / len(returns) if returns else 0.0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "max_drawdown": worst_dd,
        "worst_month": min(month_returns) if month_returns else 0.0,
        "best_month": max(month_returns) if month_returns else 0.0,
        "risk_pct": risk_pct,
        "max_positions": max_positions,
        "max_position_fraction": max_position_fraction,
        "max_total_exposure": max_total_exposure,
    }
    return summary, closed_rows


def run_grid(trades):
    rows = []
    best = None
    best_closed = None
    for risk_pct in [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02]:
        for max_positions in [2, 3, 4, 5]:
            for max_position_fraction in [1.0, 1.5, 2.0, 3.0]:
                for max_total_exposure in [2.0, 3.0, 4.0, 5.0]:
                    if max_position_fraction > max_total_exposure:
                        continue
                    summary, closed = portfolio_backtest(
                        trades,
                        risk_pct,
                        max_positions,
                        max_position_fraction,
                        max_total_exposure,
                    )
                    rows.append(summary)
                    target_ok = summary["monthly_compound"] >= 0.08
                    risk_ok = summary["max_drawdown"] > -0.45
                    key = (target_ok and risk_ok, summary["monthly_compound"], summary["profit_factor"] or 0, summary["max_drawdown"])
                    if best is None or key > best[0]:
                        best = (key, summary)
                        best_closed = closed
    return sorted(rows, key=lambda r: (r["monthly_compound"], r["profit_factor"] or 0), reverse=True), best[1], best_closed


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--since", default="2023-04-28")
    parser.add_argument("--until", default="2026-04-28")
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--adx-min", type=float, default=25)
    parser.add_argument("--stop-mult", type=float, default=2.0)
    parser.add_argument("--target-mult", type=float, default=2.0)
    parser.add_argument("--max-hold-bars", type=int, default=36)
    parser.add_argument("--fee-rate", type=float, default=0.0004)
    return parser.parse_args()


def main():
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    cfg = {
        "lookback": args.lookback,
        "adx_min": args.adx_min,
        "stop_mult": args.stop_mult,
        "target_mult": args.target_mult,
        "max_hold_bars": args.max_hold_bars,
        "fee_rate": args.fee_rate,
    }
    trades = generate_all_trades(symbols, args.since, args.until, cfg)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv([t.__dict__ for t in trades], OUT_DIR / "raw_signal_trades.csv")
    grid, best, best_closed = run_grid(trades)
    write_csv(grid, OUT_DIR / "portfolio_grid.csv")
    write_csv(best_closed, OUT_DIR / "best_portfolio_trades.csv")
    (OUT_DIR / "best_summary.json").write_text(json.dumps(best, indent=2), encoding="utf-8")
    print(json.dumps(best, indent=2))
    print("Top 10")
    print(json.dumps(grid[:10], indent=2))


if __name__ == "__main__":
    main()
