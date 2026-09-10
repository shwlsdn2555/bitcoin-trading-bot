import json
import os
import time
import traceback
import argparse
from datetime import datetime, timedelta, timezone
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


SYMBOL = os.getenv("BOT_SYMBOL", "BTC/USDT")
ENTRY_TIMEFRAME = os.getenv("BOT_ENTRY_TIMEFRAME", "5m")
TREND_TIMEFRAME = os.getenv("BOT_TREND_TIMEFRAME", "4h")

LONG_VOL_MULT = float(os.getenv("BOT_LONG_VOL_MULT", "2.618"))
SHORT_VOL_MULT = float(os.getenv("BOT_SHORT_VOL_MULT", "1.618"))
LONG_ATR_MULT = float(os.getenv("BOT_LONG_ATR_MULT", "1.618"))
SHORT_ATR_MULT = float(os.getenv("BOT_SHORT_ATR_MULT", "1.272"))
SLOPE_LOOKBACK_4H = int(os.getenv("BOT_SLOPE_LOOKBACK_4H", "12"))

TP1_LONG = float(os.getenv("BOT_TP1_LONG", "0.01272"))
TP2_LONG = float(os.getenv("BOT_TP2_LONG", "0.02000"))
TP1_SHORT = float(os.getenv("BOT_TP1_SHORT", "0.00890"))
TP2_SHORT = float(os.getenv("BOT_TP2_SHORT", "0.01218"))
SL_LONG = float(os.getenv("BOT_SL_LONG", "0.00890"))
SL_SHORT = float(os.getenv("BOT_SL_SHORT", "0.00890"))

MAX_ALERTS_PER_DAY = int(os.getenv("BOT_MAX_ALERTS_PER_DAY", "2"))
LOSS_COOLDOWN_HOURS = float(os.getenv("BOT_LOSS_COOLDOWN_HOURS", "4"))
MIN_ALERT_GAP_MINUTES = float(os.getenv("BOT_MIN_ALERT_GAP_MINUTES", "21"))
POLL_SECONDS = int(os.getenv("BOT_POLL_SECONDS", "15"))
SLIPPAGE_BPS = float(os.getenv("BOT_SLIPPAGE_BPS", "3"))

MAX_RECOMMENDED_LEVERAGE = int(os.getenv("BOT_MAX_RECOMMENDED_LEVERAGE", "10"))
LIQUIDATION_BUFFER_PCT = float(os.getenv("BOT_LIQUIDATION_BUFFER_PCT", "0.04"))
ACCOUNT_RISK_PCT = float(os.getenv("BOT_ACCOUNT_RISK_PCT", "0.005"))
MIN_SIGNAL_SCORE = int(os.getenv("BOT_MIN_SIGNAL_SCORE", "68"))
MIN_RR_TP2 = float(os.getenv("BOT_MIN_RR_TP2", "1.35"))
MIN_ADX = float(os.getenv("BOT_MIN_ADX", "18"))
MIN_ATR_PERCENTILE = float(os.getenv("BOT_MIN_ATR_PERCENTILE", "0.35"))
MAX_ATR_PERCENTILE = float(os.getenv("BOT_MAX_ATR_PERCENTILE", "0.95"))
MIN_BB_WIDTH_PCT = float(os.getenv("BOT_MIN_BB_WIDTH_PCT", "0.004"))
USE_DYNAMIC_LEVELS = os.getenv("BOT_USE_DYNAMIC_LEVELS", "true").lower() == "true"
ATR_STOP_MULT = float(os.getenv("BOT_ATR_STOP_MULT", "1.25"))
ATR_TP1_R = float(os.getenv("BOT_ATR_TP1_R", "1.20"))
ATR_TP2_R = float(os.getenv("BOT_ATR_TP2_R", "2.00"))
MAX_DYNAMIC_STOP_PCT = float(os.getenv("BOT_MAX_DYNAMIC_STOP_PCT", "0.018"))
MAX_ABS_FUNDING_RATE = float(os.getenv("BOT_MAX_ABS_FUNDING_RATE", "0.00075"))
MAX_OI_CHANGE_PCT = float(os.getenv("BOT_MAX_OI_CHANGE_PCT", "0.08"))
TRACK_ALERTS = os.getenv("BOT_TRACK_ALERTS", "true").lower() == "true"
MAX_TRACK_BARS = int(os.getenv("BOT_MAX_TRACK_BARS", "288"))
NO_TRADE_WINDOWS_UTC = os.getenv("BOT_NO_TRADE_WINDOWS_UTC", "")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
STATE_PATH = Path(os.getenv("BOT_STATE_PATH", "./state_alert_only.json"))
LOG_DIR = Path(os.getenv("BOT_LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LOG = LOG_DIR / "events_alert_only.csv"
RESULT_LOG = LOG_DIR / "alert_results.csv"


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso():
    return utc_now().isoformat()


def append_csv(path: Path, row: list, headers=None):
    first = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        import csv

        writer = csv.writer(f)
        if first and headers:
            writer.writerow(headers)
        writer.writerow(row)


def log_event(level: str, event_type: str, message: str):
    append_csv(EVENT_LOG, [utc_iso(), level, event_type, message], ["ts", "level", "event_type", "message"])
    print(f"[{level}] {event_type} | {message}")


def discord_notify(title: str, description: str, color: int = 0x5865F2):
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
            log_event("WARN", "discord_notify_fail", f"status={response.status_code} body={response.text[:200]}")
            return False
        return True
    except Exception as exc:
        log_event("WARN", "discord_notify_fail", str(exc))
        return False


def fmt_price(value: float):
    return f"{value:,.2f}"


def default_state():
    return {
        "day_key": None,
        "daily_alert_count": 0,
        "last_alert_time": None,
        "last_signal_key": None,
        "last_manual_loss_time": None,
        "open_alerts": [],
        "last_open_interest": None,
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
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    })
    exchange.load_markets()
    return exchange


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def atr(df, period=14):
    if pd is None:
        raise RuntimeError("Missing dependency: pandas. Install dependencies with: pip install -r requirements.txt")
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


def fetch_df(exchange, symbol, timeframe, limit=300):
    if pd is None:
        raise RuntimeError("Missing dependency: pandas. Install dependencies with: pip install -r requirements.txt")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna().reset_index(drop=True)


def parse_no_trade_windows():
    if not NO_TRADE_WINDOWS_UTC:
        return []
    try:
        raw = json.loads(NO_TRADE_WINDOWS_UTC)
    except Exception:
        log_event("WARN", "bad_no_trade_windows", "BOT_NO_TRADE_WINDOWS_UTC must be JSON")
        return []
    windows = []
    for item in raw:
        try:
            start = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(item["end"].replace("Z", "+00:00"))
            windows.append((start, end, item.get("reason", "scheduled no-trade window")))
        except Exception:
            log_event("WARN", "bad_no_trade_window_item", str(item))
    return windows


def current_no_trade_reason():
    now = utc_now()
    for start, end, reason in parse_no_trade_windows():
        if start <= now <= end:
            return reason
    return None


def get_derivatives_context(exchange, state):
    context = {"funding_rate": None, "open_interest": None, "oi_change_pct": None, "warnings": []}
    try:
        funding = exchange.fetch_funding_rate(SYMBOL)
        context["funding_rate"] = safe_number(funding.get("fundingRate"))
        if context["funding_rate"] is not None and abs(context["funding_rate"]) > MAX_ABS_FUNDING_RATE:
            context["warnings"].append(f"funding extreme {context['funding_rate']:.4%}")
    except Exception as exc:
        log_event("WARN", "fetch_funding_rate_fail", str(exc))

    try:
        oi = exchange.fetch_open_interest(SYMBOL)
        context["open_interest"] = safe_number(oi.get("openInterest") or oi.get("openInterestAmount"))
        previous = state.get("last_open_interest")
        if context["open_interest"] and previous:
            context["oi_change_pct"] = context["open_interest"] / previous - 1
            if abs(context["oi_change_pct"]) > MAX_OI_CHANGE_PCT:
                context["warnings"].append(f"OI jump {context['oi_change_pct']:.2%}")
        if context["open_interest"]:
            state["last_open_interest"] = context["open_interest"]
            save_state(state)
    except Exception as exc:
        log_event("WARN", "fetch_open_interest_fail", str(exc))
    return context


def safe_number(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def enrich_frames(exchange):
    if np is None:
        raise RuntimeError("Missing dependency: numpy. Install dependencies with: pip install -r requirements.txt")
    df5 = fetch_df(exchange, SYMBOL, ENTRY_TIMEFRAME, 350)
    df4 = fetch_df(exchange, SYMBOL, TREND_TIMEFRAME, 260)

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

    df4["ema21"] = ema(df4["close"], 21)
    df4["ema200"] = ema(df4["close"], 200)
    df4["atr14"] = atr(df4, 14)
    return df5, df4


def get_signal(exchange):
    df5, df4 = enrich_frames(exchange)
    if len(df5) < 120 or len(df4) < 220 + SLOPE_LOOKBACK_4H:
        return None

    sig = df5.iloc[-2]
    prev = df5.iloc[-3]
    tr = df4.iloc[-2]
    tr_past = df4.iloc[-(2 + SLOPE_LOOKBACK_4H)]

    long_cross_recent = any(
        df5.iloc[-k - 1]["ema8"] <= df5.iloc[-k - 1]["ema21"] and df5.iloc[-k]["ema8"] > df5.iloc[-k]["ema21"]
        for k in [2, 3, 4]
    )
    short_cross_recent = any(
        df5.iloc[-k - 1]["ema8"] >= df5.iloc[-k - 1]["ema21"] and df5.iloc[-k]["ema8"] < df5.iloc[-k]["ema21"]
        for k in [2, 3]
    )

    trend_up = tr["close"] > tr["ema200"] and tr["ema200"] > tr_past["ema200"]
    trend_down = tr["close"] < tr["ema200"] and tr["ema200"] < tr_past["ema200"]
    breakout_up = sig["close"] > prev["high"]
    breakout_down = sig["close"] < prev["low"]
    market_ok = (
        sig["adx14"] >= MIN_ADX
        and MIN_ATR_PERCENTILE <= sig["atr_percentile"] <= MAX_ATR_PERCENTILE
        and sig["bb_width_pct"] >= MIN_BB_WIDTH_PCT
    )

    long_cond = (
        market_ok
        and
        trend_up
        and long_cross_recent
        and sig["volume"] > sig["vol_ma21"] * LONG_VOL_MULT
        and sig["atr14"] > sig["atr14_ma21"] * LONG_ATR_MULT
        and sig["close"] > sig["open"]
        and sig["body_ratio"] >= 0.55
        and breakout_up
    )
    short_cond = (
        market_ok
        and
        trend_down
        and short_cross_recent
        and sig["volume"] > sig["vol_ma21"] * SHORT_VOL_MULT
        and sig["atr14"] > sig["atr14_ma21"] * SHORT_ATR_MULT
        and sig["close"] < sig["open"]
        and sig["body_ratio"] >= 0.50
        and breakout_down
    )

    metrics = {
        "volume_mult": float(sig["volume"] / sig["vol_ma21"]) if sig["vol_ma21"] else 0.0,
        "atr_mult": float(sig["atr14"] / sig["atr14_ma21"]) if sig["atr14_ma21"] else 0.0,
        "body_ratio": float(sig["body_ratio"]),
        "trend_gap_pct": float(abs(tr["close"] - tr["ema200"]) / tr["close"]) if tr["close"] else 0.0,
        "adx14": float(sig["adx14"]),
        "atr_percentile": float(sig["atr_percentile"]),
        "bb_width_pct": float(sig["bb_width_pct"]),
        "atr14": float(sig["atr14"]),
    }

    if long_cond:
        return {
            "side": "LONG",
            "reason": "4h uptrend + EMA cross + volume/ATR expansion + breakout",
            "candle": sig,
            "metrics": metrics,
        }
    if short_cond:
        return {
            "side": "SHORT",
            "reason": "4h downtrend + EMA cross + volume/ATR expansion + breakdown",
            "candle": sig,
            "metrics": metrics,
        }
    return None


def score_signal(signal):
    metrics = signal["metrics"]
    side = signal["side"]
    vol_base = LONG_VOL_MULT if side == "LONG" else SHORT_VOL_MULT
    atr_base = LONG_ATR_MULT if side == "LONG" else SHORT_ATR_MULT

    score = 50
    score += min(15, max(0, (metrics["volume_mult"] / vol_base - 1) * 20))
    score += min(15, max(0, (metrics["atr_mult"] / atr_base - 1) * 20))
    score += min(10, max(0, (metrics["body_ratio"] - 0.50) * 40))
    score += min(10, max(0, (metrics["adx14"] - MIN_ADX) * 0.8))
    score += min(10, metrics["trend_gap_pct"] * 500)
    score += min(5, max(0, (metrics["bb_width_pct"] - MIN_BB_WIDTH_PCT) * 500))
    score = int(round(min(100, score)))

    if score >= 80:
        grade = "A"
    elif score >= 68:
        grade = "B"
    else:
        grade = "C"
    return score, grade


def entry_price_with_slippage(price: float, side: str):
    return price * (1 + SLIPPAGE_BPS / 10000) if side == "LONG" else price * (1 - SLIPPAGE_BPS / 10000)


def build_plan(side: str, ref_price: float, atr_price: float = None):
    entry = entry_price_with_slippage(ref_price, side)
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
        tp1 = entry * (1 + tp1_pct)
        tp2 = entry * (1 + tp2_pct)
        stop = entry * (1 - stop_pct)
    else:
        tp1 = entry * (1 - tp1_pct)
        tp2 = entry * (1 - tp2_pct)
        stop = entry * (1 + stop_pct)

    recommended_leverage = max(1, min(MAX_RECOMMENDED_LEVERAGE, int(1 / max(stop_pct + LIQUIDATION_BUFFER_PCT, 0.01))))
    risk_reward_tp1 = tp1_pct / stop_pct if stop_pct else 0.0
    risk_reward_tp2 = tp2_pct / stop_pct if stop_pct else 0.0
    return {
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "stop": stop,
        "stop_pct": stop_pct,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "recommended_leverage": recommended_leverage,
        "account_risk_pct": ACCOUNT_RISK_PCT,
        "risk_reward_tp1": risk_reward_tp1,
        "risk_reward_tp2": risk_reward_tp2,
    }


def can_alert_now(state):
    now = utc_now()
    day_key = now.strftime("%Y-%m-%d")
    if state.get("day_key") != day_key:
        state["day_key"] = day_key
        state["daily_alert_count"] = 0
        save_state(state)

    if state.get("daily_alert_count", 0) >= MAX_ALERTS_PER_DAY:
        return False, "daily alert limit"
    if state.get("last_alert_time"):
        last_alert = datetime.fromisoformat(state["last_alert_time"])
        if now < last_alert + timedelta(minutes=MIN_ALERT_GAP_MINUTES):
            return False, "minimum alert gap"
    if state.get("last_manual_loss_time"):
        last_loss = datetime.fromisoformat(state["last_manual_loss_time"])
        if now < last_loss + timedelta(hours=LOSS_COOLDOWN_HOURS):
            return False, "manual loss cooldown"
    no_trade_reason = current_no_trade_reason()
    if no_trade_reason:
        return False, f"no-trade window: {no_trade_reason}"
    return True, "ok"


def append_alert_result(alert, result, touched_price, touched_ts):
    append_csv(
        RESULT_LOG,
        [
            utc_iso(),
            alert["signal_key"],
            SYMBOL,
            alert["side"],
            alert["entry"],
            alert["tp1"],
            alert["tp2"],
            alert["stop"],
            alert["score"],
            alert["grade"],
            result,
            touched_price,
            touched_ts,
        ],
        [
            "logged_at",
            "signal_key",
            "symbol",
            "side",
            "entry",
            "tp1",
            "tp2",
            "stop",
            "score",
            "grade",
            "result",
            "touched_price",
            "touched_ts",
        ],
    )


def update_open_alerts(exchange, state):
    if not TRACK_ALERTS:
        return
    open_alerts = state.get("open_alerts", [])
    if not open_alerts:
        return

    df = fetch_df(exchange, SYMBOL, ENTRY_TIMEFRAME, max(20, min(MAX_TRACK_BARS + 5, 500)))
    still_open = []
    changed = False
    for alert in open_alerts:
        alert_ts = int(alert["candle_ts"])
        rows = df[df["ts"] > alert_ts]
        result = None
        touched_price = None
        touched_ts = None

        for _, row in rows.iterrows():
            high = float(row["high"])
            low = float(row["low"])
            ts = int(row["ts"])
            if alert["side"] == "LONG":
                stop_hit = low <= alert["stop"]
                tp1_hit = high >= alert["tp1"]
                tp2_hit = high >= alert["tp2"]
            else:
                stop_hit = high >= alert["stop"]
                tp1_hit = low <= alert["tp1"]
                tp2_hit = low <= alert["tp2"]

            if stop_hit:
                result = "SL"
                touched_price = alert["stop"]
                touched_ts = ts
                break
            if tp2_hit:
                result = "TP2"
                touched_price = alert["tp2"]
                touched_ts = ts
                break
            if tp1_hit and not alert.get("tp1_seen"):
                alert["tp1_seen"] = True
                changed = True
                discord_notify(
                    f"Tracked TP1 touched - {alert['side']}",
                    f"Symbol: {SYMBOL}\nSignal: {alert['signal_key']}\nTP1: {fmt_price(alert['tp1'])}",
                    0x3498DB,
                )

        if result:
            append_alert_result(alert, result, touched_price, touched_ts)
            discord_notify(
                f"Tracked result - {result} {alert['side']}",
                f"Symbol: {SYMBOL}\nSignal: {alert['signal_key']}\nPrice: {fmt_price(touched_price)}",
                0x2ECC71 if result == "TP2" else 0xE74C3C,
            )
            changed = True
            continue

        if len(rows) >= MAX_TRACK_BARS:
            last_close = float(rows.iloc[-1]["close"])
            append_alert_result(alert, "EXPIRED", last_close, int(rows.iloc[-1]["ts"]))
            changed = True
            continue
        still_open.append(alert)

    if changed:
        state["open_alerts"] = still_open
        save_state(state)


def send_signal_alert(exchange, state, signal):
    ticker = exchange.fetch_ticker(SYMBOL)
    ref_price = float(ticker["last"])
    plan = build_plan(signal["side"], ref_price, signal["metrics"].get("atr14"))
    candle_ts = int(signal["candle"]["ts"])
    signal_key = f"{SYMBOL}:{signal['side']}:{ENTRY_TIMEFRAME}:{candle_ts}"

    if state.get("last_signal_key") == signal_key:
        return False

    side = signal["side"]
    score, grade = score_signal(signal)
    metrics = signal["metrics"]
    derivatives = get_derivatives_context(exchange, state)
    warnings = derivatives["warnings"]
    if score < MIN_SIGNAL_SCORE:
        log_event("INFO", "signal_rejected_score", f"{signal_key} score={score}")
        return False
    if plan["risk_reward_tp2"] < MIN_RR_TP2:
        log_event("INFO", "signal_rejected_rr", f"{signal_key} rr_tp2={plan['risk_reward_tp2']:.2f}")
        return False
    if warnings:
        log_event("INFO", "signal_rejected_derivatives", f"{signal_key} {'; '.join(warnings)}")
        return False

    color = 0x2ECC71 if side == "LONG" else 0xE74C3C
    description = (
        f"Symbol: {SYMBOL}\n"
        f"Direction: {side}\n"
        f"Signal grade: {grade} ({score}/100)\n"
        f"Entry zone: {fmt_price(plan['entry'])}\n"
        f"TP1: {fmt_price(plan['tp1'])} ({plan['tp1_pct']:.2%}, R:R {plan['risk_reward_tp1']:.2f})\n"
        f"TP2: {fmt_price(plan['tp2'])} ({plan['tp2_pct']:.2%}, R:R {plan['risk_reward_tp2']:.2f})\n"
        f"Stop loss: {fmt_price(plan['stop'])} ({plan['stop_pct']:.2%})\n"
        f"Recommended leverage: isolated {plan['recommended_leverage']}x or lower\n"
        f"Risk guide: account risk {plan['account_risk_pct']:.2%} if stop is hit\n"
        f"Volume/ATR/body: {metrics['volume_mult']:.2f}x / {metrics['atr_mult']:.2f}x / {metrics['body_ratio']:.2f}\n"
        f"ADX/ATR pct/BB width: {metrics['adx14']:.1f} / {metrics['atr_percentile']:.0%} / {metrics['bb_width_pct']:.2%}\n"
        f"Funding/OI change: {format_optional_pct(derivatives['funding_rate'])} / {format_optional_pct(derivatives['oi_change_pct'])}\n"
        f"Reason: {signal['reason']}\n"
        f"Candle UTC: {datetime.fromtimestamp(candle_ts / 1000, tz=timezone.utc).isoformat()}"
    )
    sent = discord_notify(f"BTC Futures Alert - {side}", description, color)
    if sent:
        state["last_signal_key"] = signal_key
        state["last_alert_time"] = utc_iso()
        state["daily_alert_count"] = state.get("daily_alert_count", 0) + 1
        state.setdefault("open_alerts", []).append({
            "signal_key": signal_key,
            "side": side,
            "entry": plan["entry"],
            "tp1": plan["tp1"],
            "tp2": plan["tp2"],
            "stop": plan["stop"],
            "score": score,
            "grade": grade,
            "candle_ts": candle_ts,
            "created_at": utc_iso(),
            "tp1_seen": False,
        })
        save_state(state)
        log_event("INFO", "signal_alert_sent", signal_key)
    return sent


def format_optional_pct(value):
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def mark_manual_loss(state):
    state["last_manual_loss_time"] = utc_iso()
    save_state(state)
    log_event("INFO", "manual_loss_marked", state["last_manual_loss_time"])
    discord_notify("Manual loss marked", f"Cooldown started for {LOSS_COOLDOWN_HOURS:g} hours", 0xF1C40F)


def send_test_discord():
    plan_long = build_plan("LONG", 100000.0)
    description = (
        "Discord connection test\n"
        f"Example entry: {fmt_price(plan_long['entry'])}\n"
        f"Example TP1/TP2: {fmt_price(plan_long['tp1'])} / {fmt_price(plan_long['tp2'])}\n"
        f"Example stop: {fmt_price(plan_long['stop'])}\n"
        f"Recommended leverage example: isolated {plan_long['recommended_leverage']}x or lower"
    )
    return discord_notify("Alert bot test", description, 0x5865F2)


def run_once(exchange, state):
    update_open_alerts(exchange, state)
    ok, reason = can_alert_now(state)
    if not ok:
        log_event("INFO", "alert_blocked", reason)
        return False
    signal = get_signal(exchange)
    if not signal:
        log_event("INFO", "no_signal", "No alert condition met")
        return False
    return send_signal_alert(exchange, state, signal)


def parse_args():
    parser = argparse.ArgumentParser(description="BTC futures alert-only bot. This bot never places orders.")
    parser.add_argument("--once", action="store_true", help="Check conditions once and exit.")
    parser.add_argument("--test-discord", action="store_true", help="Send a Discord test message and exit.")
    parser.add_argument("--mark-loss", action="store_true", help="Record a manual loss and start cooldown.")
    return parser.parse_args()


def main():
    args = parse_args()
    state = load_state()
    if args.mark_loss:
        mark_manual_loss(state)
        return
    if args.test_discord:
        send_test_discord()
        return

    exchange = create_exchange()
    if args.once:
        run_once(exchange, state)
        return

    discord_notify("Alert bot started", f"{SYMBOL} / {ENTRY_TIMEFRAME} entries / {TREND_TIMEFRAME} trend")
    log_event("INFO", "startup", f"{SYMBOL} alert-only bot started")

    while True:
        try:
            run_once(exchange, state)
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            discord_notify("Alert bot stopped", "Keyboard interrupt")
            break
        except Exception as exc:
            log_event("ERROR", "main_loop_exception", f"{exc}\n{traceback.format_exc()}")
            discord_notify("Alert bot error", f"{type(exc).__name__}: {exc}", 0xF1C40F)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
