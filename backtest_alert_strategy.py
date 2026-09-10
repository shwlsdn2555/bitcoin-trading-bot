import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    import ccxt
except ModuleNotFoundError:
    ccxt = None

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError:
    np = None
    pd = None


ENTRY_TIMEFRAME = "5m"
TREND_TIMEFRAME = "4h"
BINANCE_FUTURES_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

LONG_VOL_MULT = 2.618
SHORT_VOL_MULT = 1.618
LONG_ATR_MULT = 1.618
SHORT_ATR_MULT = 1.272
SLOPE_LOOKBACK_4H = 12

TP1_LONG = 0.01272
TP2_LONG = 0.02000
TP1_SHORT = 0.00890
TP2_SHORT = 0.01218
SL_LONG = 0.00890
SL_SHORT = 0.00890

LONG_SPLIT1 = 0.30
LONG_SPLIT2 = 0.20
SHORT_SPLIT1 = 0.55
SHORT_SPLIT2 = 0.21

SLIPPAGE_BPS = 3
FEE_RATE = 0.0004
MAX_HOLD_BARS = 288
MIN_ENTRY_GAP_BARS = 5
MIN_SIGNAL_SCORE = 68
MIN_RR_TP2 = 1.35
MIN_ADX = 18
MIN_ATR_PERCENTILE = 0.35
MAX_ATR_PERCENTILE = 0.95
MIN_BB_WIDTH_PCT = 0.004
USE_DYNAMIC_LEVELS = True
ATR_STOP_MULT = 1.25
ATR_TP1_R = 1.20
ATR_TP2_R = 2.00
MAX_DYNAMIC_STOP_PCT = 0.018


@dataclass
class Trade:
    side: str
    score: int
    grade: str
    entry_ts: int
    exit_ts: int
    entry: float
    exit: float
    tp1: float
    tp2: float
    stop: float
    gross_pct: float
    fee_pct: float
    net_pct: float
    reason: str
    bars_held: int


def require_deps():
    if pd is None or np is None:
        raise RuntimeError("Missing dependency. Install with: pip install -r requirements.txt")


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def atr(df, period=14):
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def adx(df, period=14):
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_smooth = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr_smooth
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr_smooth
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.rolling(period).mean()


def normalize_ohlcv(df):
    df = df.copy()
    for column in ["ts", "open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna().sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    return df


def load_csv(path):
    return normalize_ohlcv(pd.read_csv(path))


def save_csv(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def fetch_ohlcv(symbol, timeframe, limit):
    if ccxt is None:
        raise RuntimeError("Missing dependency: ccxt. Install with: pip install -r requirements.txt")
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    return normalize_ohlcv(pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]))


def binance_symbol(symbol):
    return symbol.replace("/", "").replace(":USDT", "")


def fetch_binance_futures_klines(symbol, timeframe, start_ms, end_ms, limit=1500):
    params = {
        "symbol": binance_symbol(symbol),
        "interval": timeframe,
        "startTime": int(start_ms),
        "endTime": int(end_ms),
        "limit": limit,
    }
    url = f"{BINANCE_FUTURES_KLINES_URL}?{urlencode(params)}"
    with urlopen(url, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    rows = []
    for item in data:
        rows.append([int(item[0]), float(item[1]), float(item[2]), float(item[3]), float(item[4]), float(item[5])])
    return rows


def fetch_ohlcv_range(symbol, timeframe, start_dt, end_dt, cache_path=None):
    if timeframe not in TIMEFRAME_MS:
        raise ValueError(f"Unsupported timeframe for range download: {timeframe}")
    if cache_path and cache_path.exists():
        return load_csv(cache_path)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    step_ms = TIMEFRAME_MS[timeframe] * 1500
    cursor = start_ms
    all_rows = []

    while cursor < end_ms:
        batch_end = min(end_ms, cursor + step_ms - TIMEFRAME_MS[timeframe])
        rows = fetch_binance_futures_klines(symbol, timeframe, cursor, batch_end)
        if not rows:
            cursor = batch_end + TIMEFRAME_MS[timeframe]
            continue
        all_rows.extend(rows)
        last_ts = rows[-1][0]
        cursor = last_ts + TIMEFRAME_MS[timeframe]
        print(f"downloaded {timeframe}: {len(all_rows)} candles, last={datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).date()}")
        time.sleep(0.12)

    df = normalize_ohlcv(pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"]))
    if cache_path:
        save_csv(df, cache_path)
    return df


def load_or_fetch(symbol, timeframe, limit, cache_dir):
    safe_symbol = symbol.replace("/", "")
    path = cache_dir / f"{safe_symbol}_{timeframe}_{limit}.csv"
    if path.exists():
        return load_csv(path)
    df = fetch_ohlcv(symbol, timeframe, limit)
    save_csv(df, path)
    return df


def prepare_frames(df5, df4):
    df5 = normalize_ohlcv(df5)
    df4 = normalize_ohlcv(df4)

    df5["ema8"] = ema(df5["close"], 8)
    df5["ema21"] = ema(df5["close"], 21)
    df5["vol_ma21"] = df5["volume"].rolling(21).mean()
    df5["body"] = (df5["close"] - df5["open"]).abs()
    candle_range = (df5["high"] - df5["low"]).replace(0, np.nan)
    df5["body_ratio"] = df5["body"] / candle_range
    df5["atr14"] = atr(df5, 14)
    df5["atr14_ma21"] = df5["atr14"].rolling(21).mean()
    df5["atr_percentile"] = df5["atr14"].rolling(120).rank(pct=True)
    df5["adx14"] = adx(df5, 14)
    bb_mid = df5["close"].rolling(20).mean()
    bb_std = df5["close"].rolling(20).std()
    df5["bb_width_pct"] = ((bb_mid + bb_std * 2) - (bb_mid - bb_std * 2)) / df5["close"]

    df4["ema200"] = ema(df4["close"], 200)
    df4["atr14"] = atr(df4, 14)

    trend = df4[["ts", "close", "ema200"]].copy()
    trend["ema200_past"] = trend["ema200"].shift(SLOPE_LOOKBACK_4H)
    trend = trend.rename(columns={"close": "trend_close"})

    df = pd.merge_asof(
        df5.sort_values("ts"),
        trend.sort_values("ts"),
        on="ts",
        direction="backward",
    )
    return df.dropna().reset_index(drop=True)


def score_signal(side, sig):
    vol_base = LONG_VOL_MULT if side == "LONG" else SHORT_VOL_MULT
    atr_base = LONG_ATR_MULT if side == "LONG" else SHORT_ATR_MULT
    volume_mult = float(sig["volume"] / sig["vol_ma21"]) if sig["vol_ma21"] else 0.0
    atr_mult = float(sig["atr14"] / sig["atr14_ma21"]) if sig["atr14_ma21"] else 0.0
    trend_gap_pct = float(abs(sig["trend_close"] - sig["ema200"]) / sig["trend_close"]) if sig["trend_close"] else 0.0
    score = 50
    score += min(15, max(0, (volume_mult / vol_base - 1) * 20))
    score += min(15, max(0, (atr_mult / atr_base - 1) * 20))
    score += min(10, max(0, (float(sig["body_ratio"]) - 0.50) * 40))
    score += min(10, max(0, (float(sig["adx14"]) - MIN_ADX) * 0.8))
    score += min(10, trend_gap_pct * 500)
    score += min(5, max(0, (float(sig["bb_width_pct"]) - MIN_BB_WIDTH_PCT) * 500))
    score = int(round(min(100, score)))
    if score >= 80:
        grade = "A"
    elif score >= 68:
        grade = "B"
    else:
        grade = "C"
    return score, grade


def plan_levels(side, entry, atr_price):
    fixed_stop_pct = SL_LONG if side == "LONG" else SL_SHORT
    if USE_DYNAMIC_LEVELS and atr_price:
        stop_pct = min(MAX_DYNAMIC_STOP_PCT, max(fixed_stop_pct, (atr_price * ATR_STOP_MULT) / entry))
        tp1_pct = max(TP1_LONG if side == "LONG" else TP1_SHORT, stop_pct * ATR_TP1_R)
        tp2_pct = max(TP2_LONG if side == "LONG" else TP2_SHORT, stop_pct * ATR_TP2_R)
    else:
        stop_pct = fixed_stop_pct
        tp1_pct = TP1_LONG if side == "LONG" else TP1_SHORT
        tp2_pct = TP2_LONG if side == "LONG" else TP2_SHORT
    if side == "LONG":
        return entry * (1 + tp1_pct), entry * (1 + tp2_pct), entry * (1 - stop_pct), stop_pct, tp1_pct, tp2_pct
    return entry * (1 - tp1_pct), entry * (1 - tp2_pct), entry * (1 + stop_pct), stop_pct, tp1_pct, tp2_pct


def signal_at(df, i):
    if i < 5:
        return None
    sig = df.iloc[i]
    prev = df.iloc[i - 1]

    long_cross_recent = any(
        df.iloc[i - k - 1]["ema8"] <= df.iloc[i - k - 1]["ema21"] and df.iloc[i - k]["ema8"] > df.iloc[i - k]["ema21"]
        for k in [1, 2, 3]
        if i - k - 1 >= 0
    )
    short_cross_recent = any(
        df.iloc[i - k - 1]["ema8"] >= df.iloc[i - k - 1]["ema21"] and df.iloc[i - k]["ema8"] < df.iloc[i - k]["ema21"]
        for k in [1, 2]
        if i - k - 1 >= 0
    )

    trend_up = sig["trend_close"] > sig["ema200"] and sig["ema200"] > sig["ema200_past"]
    trend_down = sig["trend_close"] < sig["ema200"] and sig["ema200"] < sig["ema200_past"]
    breakout_up = sig["close"] > prev["high"]
    breakout_down = sig["close"] < prev["low"]
    market_ok = (
        sig["adx14"] >= MIN_ADX
        and MIN_ATR_PERCENTILE <= sig["atr_percentile"] <= MAX_ATR_PERCENTILE
        and sig["bb_width_pct"] >= MIN_BB_WIDTH_PCT
    )

    long_cond = (
        market_ok
        and trend_up
        and long_cross_recent
        and sig["volume"] > sig["vol_ma21"] * LONG_VOL_MULT
        and sig["atr14"] > sig["atr14_ma21"] * LONG_ATR_MULT
        and sig["close"] > sig["open"]
        and sig["body_ratio"] >= 0.55
        and breakout_up
    )
    short_cond = (
        market_ok
        and trend_down
        and short_cross_recent
        and sig["volume"] > sig["vol_ma21"] * SHORT_VOL_MULT
        and sig["atr14"] > sig["atr14_ma21"] * SHORT_ATR_MULT
        and sig["close"] < sig["open"]
        and sig["body_ratio"] >= 0.50
        and breakout_down
    )

    if long_cond:
        score, grade = score_signal("LONG", sig)
        return {"side": "LONG", "score": score, "grade": grade, "atr14": float(sig["atr14"])}
    if short_cond:
        score, grade = score_signal("SHORT", sig)
        return {"side": "SHORT", "score": score, "grade": grade, "atr14": float(sig["atr14"])}
    return None


def entry_with_slippage(price, side):
    return price * (1 + SLIPPAGE_BPS / 10000) if side == "LONG" else price * (1 - SLIPPAGE_BPS / 10000)


def exit_with_slippage(price, side):
    return price * (1 - SLIPPAGE_BPS / 10000) if side == "LONG" else price * (1 + SLIPPAGE_BPS / 10000)


def simulate_trade(df, entry_i, signal):
    side = signal["side"]
    entry_bar = df.iloc[entry_i]
    entry = entry_with_slippage(float(entry_bar["open"]), side)
    tp1, tp2, stop, stop_pct, tp1_pct, tp2_pct = plan_levels(side, entry, signal.get("atr14"))
    if tp2_pct / stop_pct < MIN_RR_TP2 or signal["score"] < MIN_SIGNAL_SCORE:
        return None, entry_i

    if side == "LONG":
        split1, split2 = LONG_SPLIT1, LONG_SPLIT2
    else:
        split1, split2 = SHORT_SPLIT1, SHORT_SPLIT2

    realized = 0.0
    remaining = 1.0
    tp1_done = False
    tp2_done = False
    exit_price = entry
    reason = "MAX_HOLD"
    exit_i = min(len(df) - 1, entry_i + MAX_HOLD_BARS)

    for j in range(entry_i, min(len(df), entry_i + MAX_HOLD_BARS + 1)):
        bar = df.iloc[j]
        high = float(bar["high"])
        low = float(bar["low"])

        if side == "LONG":
            stop_hit = low <= stop
            tp1_hit = high >= tp1
            tp2_hit = high >= tp2
        else:
            stop_hit = high >= stop
            tp1_hit = low <= tp1
            tp2_hit = low <= tp2

        # Conservative same-candle rule: if stop and target both touch, assume stop first.
        if stop_hit:
            exit_price = exit_with_slippage(stop, side)
            move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
            realized += move * remaining
            reason = "STOP"
            exit_i = j
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
            exit_price = exit_with_slippage(float(bar["close"]), side)
            move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
            realized += move * remaining
            reason = "TP2_CLOSE_REST"
            exit_i = j
            break
    else:
        bar = df.iloc[exit_i]
        exit_price = exit_with_slippage(float(bar["close"]), side)
        move = (exit_price - entry) / entry if side == "LONG" else (entry - exit_price) / entry
        realized += move * remaining

    fee_pct = FEE_RATE * (1 + split1 * int(tp1_done) + split2 * int(tp2_done) + remaining)
    net_pct = realized - fee_pct
    return Trade(
        side=side,
        score=signal["score"],
        grade=signal["grade"],
        entry_ts=int(entry_bar["ts"]),
        exit_ts=int(df.iloc[exit_i]["ts"]),
        entry=entry,
        exit=exit_price,
        tp1=tp1,
        tp2=tp2,
        stop=stop,
        gross_pct=realized,
        fee_pct=fee_pct,
        net_pct=net_pct,
        reason=reason,
        bars_held=exit_i - entry_i + 1,
    ), exit_i


def run_backtest(df):
    trades = []
    i = 250
    while i < len(df) - 2:
        signal = signal_at(df, i)
        if signal:
            trade, exit_i = simulate_trade(df, i + 1, signal)
            if trade:
                trades.append(trade)
            i = max(exit_i + MIN_ENTRY_GAP_BARS, i + 1)
        else:
            i += 1
    return trades


def max_drawdown(returns):
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for ret in returns:
        equity *= 1 + ret
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst


def summarize(trades):
    returns = [t.net_pct for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total_return = math.prod([1 + r for r in returns]) - 1 if returns else 0.0
    by_side = {}
    for side in ["LONG", "SHORT"]:
        side_returns = [t.net_pct for t in trades if t.side == side]
        side_wins = [r for r in side_returns if r > 0]
        by_side[side] = {
            "trades": len(side_returns),
            "win_rate": len(side_wins) / len(side_returns) if side_returns else 0.0,
            "avg_net_pct": sum(side_returns) / len(side_returns) if side_returns else 0.0,
        }
    by_grade = {}
    for grade in ["A", "B", "C"]:
        grade_returns = [t.net_pct for t in trades if t.grade == grade]
        grade_wins = [r for r in grade_returns if r > 0]
        by_grade[grade] = {
            "trades": len(grade_returns),
            "win_rate": len(grade_wins) / len(grade_returns) if grade_returns else 0.0,
            "avg_net_pct": sum(grade_returns) / len(grade_returns) if grade_returns else 0.0,
        }
    return {
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "avg_net_pct": sum(returns) / len(returns) if returns else 0.0,
        "total_compounded_return": total_return,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "max_drawdown": max_drawdown(returns),
        "best_trade": max(returns) if returns else 0.0,
        "worst_trade": min(returns) if returns else 0.0,
        "by_side": by_side,
        "by_grade": by_grade,
    }


def monthly_summary(trades):
    buckets = {}
    for trade in trades:
        month = datetime.fromtimestamp(trade.entry_ts / 1000, tz=timezone.utc).strftime("%Y-%m")
        buckets.setdefault(month, []).append(trade.net_pct)
    rows = []
    for month, returns in sorted(buckets.items()):
        wins = [r for r in returns if r > 0]
        rows.append({
            "month": month,
            "trades": len(returns),
            "win_rate": len(wins) / len(returns) if returns else 0.0,
            "avg_net_pct": sum(returns) / len(returns) if returns else 0.0,
            "compounded_return": math.prod([1 + r for r in returns]) - 1 if returns else 0.0,
        })
    return rows


def write_monthly(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["month", "trades", "win_rate", "avg_net_pct", "compounded_return"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_trades(trades, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(Trade.__dataclass_fields__.keys()) + ["entry_time_utc", "exit_time_utc"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            row = trade.__dict__.copy()
            row["entry_time_utc"] = datetime.fromtimestamp(trade.entry_ts / 1000, tz=timezone.utc).isoformat()
            row["exit_time_utc"] = datetime.fromtimestamp(trade.exit_ts / 1000, tz=timezone.utc).isoformat()
            writer.writerow(row)


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest the alert-only BTC futures strategy.")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--entry-csv", help="Optional 5m OHLCV CSV with ts,open,high,low,close,volume")
    parser.add_argument("--trend-csv", help="Optional 4h OHLCV CSV with ts,open,high,low,close,volume")
    parser.add_argument("--entry-limit", type=int, default=1500)
    parser.add_argument("--trend-limit", type=int, default=1000)
    parser.add_argument("--years", type=float, default=None, help="Download this many years of Binance futures data.")
    parser.add_argument("--since", help="UTC start date, e.g. 2023-04-28")
    parser.add_argument("--until", help="UTC end date, e.g. 2026-04-28")
    parser.add_argument("--cache-dir", default="./data")
    parser.add_argument("--out-dir", default="./backtest_results")
    return parser.parse_args()


def parse_utc_date(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def main():
    require_deps()
    args = parse_args()
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)

    if args.entry_csv:
        df5 = load_csv(args.entry_csv)
    elif args.years or args.since:
        end_dt = parse_utc_date(args.until) if args.until else datetime.now(timezone.utc)
        start_dt = parse_utc_date(args.since) if args.since else end_dt - timedelta(days=365.25 * args.years)
        safe_symbol = binance_symbol(args.symbol)
        date_key = f"{start_dt.date()}_{end_dt.date()}"
        df5 = fetch_ohlcv_range(args.symbol, ENTRY_TIMEFRAME, start_dt, end_dt, cache_dir / f"{safe_symbol}_{ENTRY_TIMEFRAME}_{date_key}.csv")
    else:
        df5 = load_or_fetch(args.symbol, ENTRY_TIMEFRAME, args.entry_limit, cache_dir)

    if args.trend_csv:
        df4 = load_csv(args.trend_csv)
    elif args.years or args.since:
        # Pull extra 4h history so EMA200 and slope are warmed up before the 5m test period.
        trend_start = start_dt - timedelta(days=120)
        safe_symbol = binance_symbol(args.symbol)
        date_key = f"{trend_start.date()}_{end_dt.date()}"
        df4 = fetch_ohlcv_range(args.symbol, TREND_TIMEFRAME, trend_start, end_dt, cache_dir / f"{safe_symbol}_{TREND_TIMEFRAME}_{date_key}.csv")
    else:
        df4 = load_or_fetch(args.symbol, TREND_TIMEFRAME, args.trend_limit, cache_dir)

    merged = prepare_frames(df5, df4)
    trades = run_backtest(merged)
    summary = summarize(trades)

    trades_path = out_dir / "trades.csv"
    summary_path = out_dir / "summary.json"
    monthly_path = out_dir / "monthly.csv"
    write_trades(trades, trades_path)
    write_monthly(monthly_summary(trades), monthly_path)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Trades: {trades_path}")
    print(f"Monthly: {monthly_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
