import csv
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import backtest_alert_strategy as bt


DATA_DIR = Path("./data_3y")
OUT_DIR = Path("./optimization_results")
SYMBOL_KEY = "BTCUSDT"
ENTRY_CSV = DATA_DIR / f"{SYMBOL_KEY}_5m_2023-04-28_2026-04-28.csv"
TREND_CSV = DATA_DIR / f"{SYMBOL_KEY}_4h_2022-12-29_2026-04-28.csv"


def load_frames():
    if not ENTRY_CSV.exists() or not TREND_CSV.exists():
        raise RuntimeError("Run the 3-year backtest first so data_3y CSV files exist.")
    df5 = bt.load_csv(ENTRY_CSV)
    df4 = bt.load_csv(TREND_CSV)
    df = bt.prepare_frames(df5, df4)
    return df.reset_index(drop=True)


def precompute_candidates(df):
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)

    long_cross = pd.Series(False, index=df.index)
    for k in [1, 2, 3, 4, 5, 6]:
        long_cross |= (df["ema8"].shift(k + 1) <= df["ema21"].shift(k + 1)) & (df["ema8"].shift(k) > df["ema21"].shift(k))

    short_cross = pd.Series(False, index=df.index)
    for k in [1, 2, 3, 4, 5, 6]:
        short_cross |= (df["ema8"].shift(k + 1) >= df["ema21"].shift(k + 1)) & (df["ema8"].shift(k) < df["ema21"].shift(k))

    trend_up = (df["trend_close"] > df["ema200"]) & (df["ema200"] > df["ema200_past"])
    trend_down = (df["trend_close"] < df["ema200"]) & (df["ema200"] < df["ema200_past"])

    base = pd.DataFrame({
        "i": np.arange(len(df)),
        "ts": df["ts"].values,
        "side_long": trend_up & long_cross & (df["close"] > df["open"]) & (df["close"] > prev_high),
        "side_short": trend_down & short_cross & (df["close"] < df["open"]) & (df["close"] < prev_low),
        "volume_mult": (df["volume"] / df["vol_ma21"]).replace([np.inf, -np.inf], np.nan),
        "atr_mult": (df["atr14"] / df["atr14_ma21"]).replace([np.inf, -np.inf], np.nan),
        "body_ratio": df["body_ratio"],
        "adx14": df["adx14"],
        "atr_percentile": df["atr_percentile"],
        "bb_width_pct": df["bb_width_pct"],
        "atr14": df["atr14"],
        "trend_gap_pct": ((df["trend_close"] - df["ema200"]).abs() / df["trend_close"]).replace([np.inf, -np.inf], np.nan),
    })
    return base.dropna().reset_index(drop=True)


def score_row(row, side, long_vol, short_vol, long_atr, short_atr, min_adx, min_bb):
    vol_base = long_vol if side == "LONG" else short_vol
    atr_base = long_atr if side == "LONG" else short_atr
    score = 50
    score += min(15, max(0, (row.volume_mult / vol_base - 1) * 20))
    score += min(15, max(0, (row.atr_mult / atr_base - 1) * 20))
    score += min(10, max(0, (row.body_ratio - 0.50) * 40))
    score += min(10, max(0, (row.adx14 - min_adx) * 0.8))
    score += min(10, row.trend_gap_pct * 500)
    score += min(5, max(0, (row.bb_width_pct - min_bb) * 500))
    score = int(round(min(100, score)))
    if score >= 80:
        grade = "A"
    elif score >= 68:
        grade = "B"
    else:
        grade = "C"
    return score, grade


def levels(side, entry, atr_price, mode, stop_mult, tp1_r, tp2_r):
    if side == "LONG":
        fixed_stop, fixed_tp1, fixed_tp2 = bt.SL_LONG, bt.TP1_LONG, bt.TP2_LONG
    else:
        fixed_stop, fixed_tp1, fixed_tp2 = bt.SL_SHORT, bt.TP1_SHORT, bt.TP2_SHORT
    if mode == "atr":
        stop_pct = min(0.022, max(fixed_stop, (atr_price * stop_mult) / entry))
        tp1_pct = max(fixed_tp1, stop_pct * tp1_r)
        tp2_pct = max(fixed_tp2, stop_pct * tp2_r)
    else:
        stop_pct, tp1_pct, tp2_pct = fixed_stop, fixed_tp1, fixed_tp2
    if side == "LONG":
        return entry * (1 + tp1_pct), entry * (1 + tp2_pct), entry * (1 - stop_pct), stop_pct, tp1_pct, tp2_pct
    return entry * (1 - tp1_pct), entry * (1 - tp2_pct), entry * (1 + stop_pct), stop_pct, tp1_pct, tp2_pct


def simulate(df, entry_i, side, atr_price, mode, stop_mult, tp1_r, tp2_r, max_hold):
    if entry_i >= len(df):
        return None, entry_i
    entry = bt.entry_with_slippage(float(df.at[entry_i, "open"]), side)
    tp1, tp2, stop, stop_pct, tp1_pct, tp2_pct = levels(side, entry, atr_price, mode, stop_mult, tp1_r, tp2_r)
    split1, split2 = (bt.LONG_SPLIT1, bt.LONG_SPLIT2) if side == "LONG" else (bt.SHORT_SPLIT1, bt.SHORT_SPLIT2)

    realized = 0.0
    remaining = 1.0
    tp1_done = False
    tp2_done = False
    exit_i = min(len(df) - 1, entry_i + max_hold)
    reason = "MAX_HOLD"

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()

    for j in range(entry_i, min(len(df), entry_i + max_hold + 1)):
        high = float(highs[j])
        low = float(lows[j])
        if side == "LONG":
            stop_hit = low <= stop
            tp1_hit = high >= tp1
            tp2_hit = high >= tp2
        else:
            stop_hit = high >= stop
            tp1_hit = low <= tp1
            tp2_hit = low <= tp2

        if stop_hit:
            exit_price = bt.exit_with_slippage(stop, side)
            move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
            realized += move * remaining
            exit_i = j
            reason = "STOP"
            break
        if not tp1_done and tp1_hit:
            realized += tp1_pct * split1
            remaining -= split1
            tp1_done = True
        if tp1_done and not tp2_done and tp2_hit:
            realized += tp2_pct * split2
            remaining -= split2
            tp2_done = True
        if tp2_done:
            exit_price = bt.exit_with_slippage(float(closes[j]), side)
            move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
            realized += move * remaining
            exit_i = j
            reason = "TP2_CLOSE_REST"
            break
    else:
        exit_price = bt.exit_with_slippage(float(closes[exit_i]), side)
        move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
        realized += move * remaining

    fee_pct = bt.FEE_RATE * (1 + split1 * int(tp1_done) + split2 * int(tp2_done) + remaining)
    return {
        "side": side,
        "entry_ts": int(df.at[entry_i, "ts"]),
        "net_pct": realized - fee_pct,
        "reason": reason,
        "bars_held": exit_i - entry_i + 1,
    }, exit_i


def summarize(returns):
    if not returns:
        return {"trades": 0, "win_rate": 0.0, "avg_net_pct": 0.0, "total": 0.0, "profit_factor": None, "mdd": 0.0}
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(returns),
        "win_rate": len(wins) / len(returns),
        "avg_net_pct": sum(returns) / len(returns),
        "total": math.prod([1 + r for r in returns]) - 1,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "mdd": bt.max_drawdown(returns),
    }


def run_config(df, candidates, cfg):
    selected = []
    for row in candidates.itertuples(index=False):
        sides = []
        if cfg["side"] in ["BOTH", "LONG"] and row.side_long:
            sides.append("LONG")
        if cfg["side"] in ["BOTH", "SHORT"] and row.side_short:
            sides.append("SHORT")
        for side in sides:
            vol_req = cfg["long_vol"] if side == "LONG" else cfg["short_vol"]
            atr_req = cfg["long_atr"] if side == "LONG" else cfg["short_atr"]
            if row.volume_mult < vol_req or row.atr_mult < atr_req:
                continue
            if row.body_ratio < cfg["body"]:
                continue
            if row.adx14 < cfg["min_adx"]:
                continue
            if not (cfg["min_atr_pct"] <= row.atr_percentile <= cfg["max_atr_pct"]):
                continue
            if row.bb_width_pct < cfg["min_bb"]:
                continue
            score, grade = score_row(row, side, cfg["long_vol"], cfg["short_vol"], cfg["long_atr"], cfg["short_atr"], cfg["min_adx"], cfg["min_bb"])
            if score < cfg["min_score"]:
                continue
            selected.append((int(row.i), side, float(row.atr14), score, grade))

    trades = []
    cursor = 250
    for i, side, atr_price, score, grade in selected:
        if i < cursor or i + 1 >= len(df):
            continue
        trade, exit_i = simulate(df, i + 1, side, atr_price, cfg["level_mode"], cfg["stop_mult"], cfg["tp1_r"], cfg["tp2_r"], cfg["max_hold"])
        if trade:
            trade["score"] = score
            trade["grade"] = grade
            trades.append(trade)
        cursor = max(exit_i + cfg["gap"], i + 1)

    returns = [t["net_pct"] for t in trades]
    result = summarize(returns)
    result.update(cfg)
    result["stop_rate"] = sum(1 for t in trades if t["reason"] == "STOP") / len(trades) if trades else 0.0
    return result, trades


def config_grid():
    base = {
        "gap": 5,
        "max_hold": 288,
        "tp1_r": 1.2,
        "tp2_r": 2.0,
        "stop_mult": 1.25,
    }
    for side in ["BOTH", "LONG", "SHORT"]:
        for level_mode in ["fixed", "atr"]:
            for min_score in [55, 60, 68, 75, 80]:
                for min_adx in [12, 16, 20, 25]:
                    for min_atr_pct, max_atr_pct in [(0.15, 0.98), (0.25, 0.95), (0.35, 0.95), (0.45, 0.90)]:
                        for body in [0.45, 0.50, 0.55]:
                            cfg = dict(base)
                            cfg.update({
                                "side": side,
                                "level_mode": level_mode,
                                "min_score": min_score,
                                "min_adx": min_adx,
                                "min_atr_pct": min_atr_pct,
                                "max_atr_pct": max_atr_pct,
                                "min_bb": 0.0025,
                                "body": body,
                                "long_vol": 1.4,
                                "short_vol": 1.4,
                                "long_atr": 1.0,
                                "short_atr": 1.0,
                            })
                            yield cfg


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    df = load_frames()
    candidates = precompute_candidates(df)
    rows = []
    best_trades = None
    best_key = None
    for n, cfg in enumerate(config_grid(), 1):
        result, trades = run_config(df, candidates, cfg)
        rows.append(result)
        eligible = result["trades"] >= 100 and result["profit_factor"] is not None
        key = (eligible, result["total"], result["profit_factor"] or 0, -abs(result["mdd"]))
        if best_key is None or key > best_key:
            best_key = key
            best_trades = trades
        if n % 250 == 0:
            print(f"tested {n} configs")

    rows = sorted(rows, key=lambda r: (r["trades"] >= 100, r["total"], r["profit_factor"] or 0), reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, OUT_DIR / "optimization_summary.csv")
    write_csv(best_trades or [], OUT_DIR / "best_trades.csv")
    print(json.dumps(rows[:20], indent=2))


if __name__ == "__main__":
    main()
