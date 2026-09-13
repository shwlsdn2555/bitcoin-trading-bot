import argparse
import csv
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

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

try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


SYMBOLS = [s.strip() for s in os.getenv("BOT_SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT").split(",") if s.strip()]
TIMEFRAME = os.getenv("BOT_TIMEFRAME", "4h")
LOOKBACK = int(os.getenv("BOT_DONCHIAN_LOOKBACK", "10"))
ADX_MIN = float(os.getenv("BOT_ADX_MIN", "20"))
STOP_ATR_MULT = float(os.getenv("BOT_STOP_ATR_MULT", "2.0"))
TARGET_ATR_MULT = float(os.getenv("BOT_TARGET_ATR_MULT", "4.0"))
MAX_HOLD_BARS = int(os.getenv("BOT_MAX_HOLD_BARS", "24"))

RISK_PCT = float(os.getenv("BOT_RISK_PCT", "0.03"))
MAX_POSITIONS = int(os.getenv("BOT_MAX_POSITIONS", "2"))
MAX_SAME_SIDE = int(os.getenv("BOT_MAX_SAME_SIDE", "1"))
MAX_POSITION_FRACTION = float(os.getenv("BOT_MAX_POSITION_FRACTION", "1.5"))
MAX_TOTAL_EXPOSURE = float(os.getenv("BOT_MAX_TOTAL_EXPOSURE", "3.0"))
MONTHLY_REDUCE_AT = float(os.getenv("BOT_MONTHLY_REDUCE_AT", "-0.06"))
MONTHLY_STOP_AT = float(os.getenv("BOT_MONTHLY_STOP_AT", "-0.10"))
VOL_FILTER = os.getenv("BOT_VOL_FILTER", "none").strip().lower()

STABLE_RISK_PCT = float(os.getenv("BOT_STABLE_RISK_PCT", "0.015"))
AGGRESSIVE_RISK_PCT = float(os.getenv("BOT_AGGRESSIVE_RISK_PCT", "0.04"))
POLL_SECONDS = int(os.getenv("BOT_POLL_SECONDS", "300"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
STATE_PATH = Path(os.getenv("BOT_STATE_PATH", "./state_swing_portfolio.json"))
LOG_DIR = Path(os.getenv("BOT_LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LOG = LOG_DIR / "events_swing_portfolio.csv"
RESULT_LOG = LOG_DIR / "swing_alert_results.csv"


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso():
    return utc_now().isoformat()


def month_key(ts=None):
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else utc_now()
    return dt.strftime("%Y-%m")


def append_csv(path, row, headers):
    first = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if first:
            writer.writerow(headers)
        writer.writerow(row)


def log_event(level, event_type, message):
    append_csv(EVENT_LOG, [utc_iso(), level, event_type, message], ["ts", "level", "event_type", "message"])
    print(f"[{level}] {event_type} | {message}")


def discord_notify(title, description, color=0x5865F2):
    if requests is None:
        log_event("ERROR", "missing_dependency", "Install dependencies with: pip install -r requirements.txt")
        return False
    if not DISCORD_WEBHOOK_URL:
        log_event("WARN", "discord_skipped", "DISCORD_WEBHOOK_URL is empty")
        return False
    payload = {"embeds": [{"title": title, "description": description, "color": color, "timestamp": utc_iso()}]}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code >= 300:
            log_event("WARN", "discord_fail", f"{response.status_code} {response.text[:200]}")
            return False
        return True
    except Exception as exc:
        log_event("WARN", "discord_fail", str(exc))
        return False


def default_state():
    return {
        "last_signal_keys": {},
        "open_alerts": [],
        "monthly_pnl": {},
        "paused_months": [],
    }


def load_state():
    if not STATE_PATH.exists():
        return default_state()
    try:
        return {**default_state(), **json.loads(STATE_PATH.read_text(encoding="utf-8"))}
    except Exception:
        return default_state()


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def create_exchange():
    if ccxt is None:
        raise RuntimeError("Missing dependency: ccxt. Install dependencies with: pip install -r requirements.txt")
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future", "adjustForTimeDifference": True}})
    exchange.load_markets()
    return exchange


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


def fetch_df(exchange, symbol, limit=260):
    if pd is None or np is None:
        raise RuntimeError("Missing dependency: pandas/numpy. Install dependencies with: pip install -r requirements.txt")
    rows = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=limit)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["atr14"] = atr(df, 14)
    df["adx14"] = adx(df, 14)
    df["atr_pctile"] = df["atr14"].rolling(180).rank(pct=True)
    return df.dropna().reset_index(drop=True)


def fmt_price(value):
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:,.4f}"
    return f"{value:,.6f}"


def active_alerts(state):
    now_ms = int(time.time() * 1000)
    max_age_ms = MAX_HOLD_BARS * 4 * 60 * 60 * 1000
    return [a for a in state.get("open_alerts", []) if now_ms - int(a["entry_ts"]) <= max_age_ms and not a.get("closed")]


def projected_monthly_risk(state):
    mk = month_key()
    pnl = state.get("monthly_pnl", {}).get(mk, 0.0)
    if mk in state.get("paused_months", []):
        return 0.0, "monthly stop active"
    if pnl <= MONTHLY_STOP_AT:
        state.setdefault("paused_months", []).append(mk)
        save_state(state)
        return 0.0, "monthly stop hit"
    if pnl <= MONTHLY_REDUCE_AT:
        return RISK_PCT * 0.5, "monthly drawdown reduction"
    return RISK_PCT, "normal"


def portfolio_allows(state, side, position_fraction):
    alerts = active_alerts(state)
    if len(alerts) >= MAX_POSITIONS:
        return False, "max positions reached"
    same_side = sum(1 for a in alerts if a["side"] == side)
    if same_side >= MAX_SAME_SIDE:
        return False, "same-side position limit"
    exposure = sum(float(a.get("position_fraction", 0.0)) for a in alerts)
    if exposure + position_fraction > MAX_TOTAL_EXPOSURE:
        return False, "total exposure limit"
    return True, "ok"


def build_signal(exchange, symbol, state):
    df = fetch_df(exchange, symbol)
    if len(df) < 220 + LOOKBACK:
        return None
    sig = df.iloc[-2]
    previous = df.iloc[-(LOOKBACK + 2):-2]
    donchian_high = float(previous["high"].max())
    donchian_low = float(previous["low"].min())
    side = None
    if sig["close"] > donchian_high and sig["ema50"] > sig["ema200"] and sig["adx14"] > ADX_MIN:
        side = "LONG"
    elif sig["close"] < donchian_low and sig["ema50"] < sig["ema200"] and sig["adx14"] > ADX_MIN:
        side = "SHORT"
    if not side:
        return None

    candle_ts = int(sig["ts"])
    signal_key = f"{symbol}:{TIMEFRAME}:{side}:{candle_ts}"
    if state.get("last_signal_keys", {}).get(symbol) == signal_key:
        return None

    ticker = exchange.fetch_ticker(symbol)
    entry = float(ticker.get("last") or sig["close"])
    atr_price = float(sig["atr14"])
    if side == "LONG":
        stop = entry - atr_price * STOP_ATR_MULT
        target = entry + atr_price * TARGET_ATR_MULT
    else:
        stop = entry + atr_price * STOP_ATR_MULT
        target = entry - atr_price * TARGET_ATR_MULT
    atr_pctile = float(sig.get("atr_pctile", 0.0))
    if VOL_FILTER == "skip_extreme" and atr_pctile >= 0.95:
        log_event("INFO", "signal_blocked", f"{signal_key} extreme volatility filter atr_pctile={atr_pctile:.2f}")
        return None
    stop_pct = abs(entry - stop) / entry
    risk_pct, risk_reason = projected_monthly_risk(state)
    if risk_pct <= 0:
        log_event("INFO", "signal_blocked", f"{signal_key} {risk_reason}")
        return None

    position_fraction = min(MAX_POSITION_FRACTION, risk_pct / max(stop_pct, 0.001))
    allowed, block_reason = portfolio_allows(state, side, position_fraction)
    if not allowed:
        log_event("INFO", "signal_blocked", f"{signal_key} {block_reason}")
        return None

    stable_fraction = min(MAX_POSITION_FRACTION, STABLE_RISK_PCT / max(stop_pct, 0.001))
    aggressive_fraction = min(MAX_POSITION_FRACTION, AGGRESSIVE_RISK_PCT / max(stop_pct, 0.001))
    return {
        "symbol": symbol,
        "side": side,
        "signal_key": signal_key,
        "candle_ts": candle_ts,
        "entry_ts": int(time.time() * 1000),
        "entry": entry,
        "stop": stop,
        "target": target,
        "stop_pct": stop_pct,
        "atr": atr_price,
        "atr_pctile": atr_pctile,
        "adx": float(sig["adx14"]),
        "ema50": float(sig["ema50"]),
        "ema200": float(sig["ema200"]),
        "position_fraction": position_fraction,
        "stable_fraction": stable_fraction,
        "aggressive_fraction": aggressive_fraction,
        "risk_pct": risk_pct,
        "risk_reason": risk_reason,
        "closed": False,
    }


def send_signal(signal):
    color = 0x2ECC71 if signal["side"] == "LONG" else 0xE74C3C
    hold_days = MAX_HOLD_BARS * 4 / 24
    desc = (
        f"Symbol: {signal['symbol']}\n"
        f"Direction: {signal['side']}\n"
        f"Strategy: 4H Donchian {LOOKBACK} Swing\n"
        f"Entry zone: {fmt_price(signal['entry'])}\n"
        f"Stop: {fmt_price(signal['stop'])} ({signal['stop_pct']:.2%})\n"
        f"Target: {fmt_price(signal['target'])} (R:R {(TARGET_ATR_MULT / STOP_ATR_MULT):.2f})\n"
        f"Max hold: {MAX_HOLD_BARS} candles (~{hold_days:.1f} days)\n"
        f"ADX: {signal['adx']:.1f}\n"
        f"ATR: {fmt_price(signal['atr'])} / percentile {signal['atr_pctile']:.0%}\n"
        f"Default risk: {signal['risk_pct']:.2%} ({signal['risk_reason']})\n"
        f"Default notional: {signal['position_fraction']:.2f}x equity\n"
        f"Stable mode: risk {STABLE_RISK_PCT:.2%}, notional {signal['stable_fraction']:.2f}x\n"
        f"Aggressive mode: risk {AGGRESSIVE_RISK_PCT:.2%}, notional {signal['aggressive_fraction']:.2f}x\n"
        f"Portfolio rule: max {MAX_POSITIONS} positions, max {MAX_SAME_SIDE} same-side"
    )
    return discord_notify(f"Swing Alert - {signal['symbol']} {signal['side']}", desc, color)


def record_result(state, alert, result, touched_price):
    net_on_notional = ((touched_price - alert["entry"]) / alert["entry"]) if alert["side"] == "LONG" else ((alert["entry"] - touched_price) / alert["entry"])
    equity_return = net_on_notional * float(alert["position_fraction"])
    mk = month_key(int(alert["entry_ts"]))
    state.setdefault("monthly_pnl", {})[mk] = state.setdefault("monthly_pnl", {}).get(mk, 0.0) + equity_return
    append_csv(
        RESULT_LOG,
        [
            utc_iso(),
            alert["signal_key"],
            alert["symbol"],
            alert["side"],
            result,
            alert["entry"],
            touched_price,
            alert["position_fraction"],
            equity_return,
            state["monthly_pnl"][mk],
        ],
        ["logged_at", "signal_key", "symbol", "side", "result", "entry", "touched_price", "position_fraction", "equity_return", "month_pnl"],
    )
    discord_notify(
        f"Swing Result - {alert['symbol']} {result}",
        f"Signal: {alert['side']}\nPrice: {fmt_price(touched_price)}\nEstimated account impact: {equity_return:.2%}\nMonth tracked PnL: {state['monthly_pnl'][mk]:.2%}",
        0x2ECC71 if result == "TARGET" else 0xE74C3C,
    )


def update_open_alerts(exchange, state):
    alerts = state.get("open_alerts", [])
    if not alerts:
        return
    changed = False
    kept = []
    for alert in alerts:
        if alert.get("closed"):
            continue
        df = fetch_df(exchange, alert["symbol"], limit=max(80, MAX_HOLD_BARS + 20))
        rows = df[df["ts"] > int(alert["candle_ts"])]
        result = None
        touched = None
        for _, row in rows.iterrows():
            high = float(row["high"])
            low = float(row["low"])
            if alert["side"] == "LONG":
                if low <= alert["stop"]:
                    result, touched = "STOP", alert["stop"]
                    break
                if high >= alert["target"]:
                    result, touched = "TARGET", alert["target"]
                    break
            else:
                if high >= alert["stop"]:
                    result, touched = "STOP", alert["stop"]
                    break
                if low <= alert["target"]:
                    result, touched = "TARGET", alert["target"]
                    break
        if result:
            record_result(state, alert, result, touched)
            changed = True
            continue
        if len(rows) >= MAX_HOLD_BARS:
            close_price = float(rows.iloc[-1]["close"])
            record_result(state, alert, "TIME", close_price)
            changed = True
            continue
        kept.append(alert)
    if changed:
        state["open_alerts"] = kept
        save_state(state)


def scan_once(exchange, state):
    update_open_alerts(exchange, state)
    for symbol in SYMBOLS:
        try:
            signal = build_signal(exchange, symbol, state)
            if not signal:
                continue
            if send_signal(signal):
                state.setdefault("last_signal_keys", {})[symbol] = signal["signal_key"]
                state.setdefault("open_alerts", []).append(signal)
                save_state(state)
                log_event("INFO", "signal_sent", signal["signal_key"])
        except Exception as exc:
            log_event("WARN", "symbol_scan_failed", f"{symbol}: {exc}")


def send_test():
    return discord_notify(
        "Swing portfolio bot test",
        f"Symbols: {', '.join(SYMBOLS)}\nTimeframe: {TIMEFRAME}\nRisk: {RISK_PCT:.2%}\nMax positions: {MAX_POSITIONS}",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Alert-only multi-coin 4H swing portfolio bot. It never places orders.")
    parser.add_argument("--once", action="store_true", help="Scan once and exit.")
    parser.add_argument("--test-discord", action="store_true", help="Send a test Discord message and exit.")
    return parser.parse_args()


def main():
    args = parse_args()
    state = load_state()
    if args.test_discord:
        send_test()
        return
    exchange = create_exchange()
    if args.once:
        scan_once(exchange, state)
        return
    discord_notify("Swing portfolio bot started", f"{', '.join(SYMBOLS)} / {TIMEFRAME} / alert-only")
    while True:
        try:
            scan_once(exchange, state)
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            discord_notify("Swing portfolio bot stopped", "Keyboard interrupt")
            break
        except Exception as exc:
            log_event("ERROR", "main_loop_exception", f"{exc}\n{traceback.format_exc()}")
            discord_notify("Swing portfolio bot error", f"{type(exc).__name__}: {exc}", 0xF1C40F)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
