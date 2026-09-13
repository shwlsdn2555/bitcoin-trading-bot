"""Validate preselected stable-profile candidates on an untouched later period."""

import json
from datetime import datetime, timezone
from pathlib import Path

from portfolio_swing_backtest import write_csv
from risk_research_backtest import SYMBOLS, btc_daily_regime, generate_trades, portfolio


OUT_DIR = Path("./risk_research_results")
TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"
TEST_END = "2026-04-28"

CANDIDATES = (
    {
        "name": "stable_five_symbol_baseline",
        "symbols": SYMBOLS,
        "monthly_reduce_at": -0.08,
        "monthly_stop_at": -0.12,
    },
    {
        "name": "p1_monthly_loss_defense",
        "symbols": SYMBOLS,
        "monthly_reduce_at": -0.06,
        "monthly_stop_at": -0.08,
    },
    {
        "name": "p2_symbol_pruning",
        "symbols": ["ETH/USDT", "BNB/USDT", "XRP/USDT"],
        "monthly_reduce_at": -0.08,
        "monthly_stop_at": -0.12,
    },
)


def timestamp(date_string):
    return int(datetime.fromisoformat(date_string).replace(tzinfo=timezone.utc).timestamp() * 1000)


def period_months(start, end):
    return (timestamp(end) - timestamp(start)) / 1000 / 86400 / (365.25 / 12)


def stable_config(candidate):
    return {
        "risk_pct": 0.025,
        "max_positions": 2,
        "max_same_side": 1,
        "max_position_fraction": 1.5,
        "max_total_exposure": 3.0,
        "regime_filter": "none",
        "vol_filter": "skip_extreme",
        "monthly_reduce_at": candidate["monthly_reduce_at"],
        "monthly_stop_at": candidate["monthly_stop_at"],
    }


def evaluate(candidate, trades, regimes, start=None, end=None):
    selected = [trade for trade in trades if trade["symbol"] in candidate["symbols"]]
    if start is not None:
        selected = [trade for trade in selected if trade["entry_ts"] >= timestamp(start)]
    if end is not None:
        selected = [trade for trade in selected if trade["entry_ts"] <= timestamp(end)]
    summary, _ = portfolio(selected, stable_config(candidate), regimes)
    if start and end:
        summary["monthly_compound"] = (1 + summary["total_return"]) ** (1 / period_months(start, end)) - 1
    return {
        "candidate": candidate["name"],
        "symbols": ",".join(candidate["symbols"]),
        "monthly_reduce_at": candidate["monthly_reduce_at"],
        "monthly_stop_at": candidate["monthly_stop_at"],
        **summary,
    }


def candidate_decision(train, test, baseline_test):
    if train["candidate"] == "stable_five_symbol_baseline":
        return "baseline"
    train_qualified = train["monthly_compound"] >= 0.04 and train["max_drawdown"] >= -0.22 and (train["profit_factor"] or 0) >= 1.35
    test_improves_drawdown = test["max_drawdown"] >= baseline_test["max_drawdown"]
    test_improves_pf = (test["profit_factor"] or 0) >= (baseline_test["profit_factor"] or 0)
    test_preserves_return = test["monthly_compound"] >= baseline_test["monthly_compound"] - 0.002
    if train_qualified and test_improves_drawdown and test_improves_pf and test_preserves_return:
        return "validated_candidate"
    return "rejected_on_holdout"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    regimes = btc_daily_regime()
    trades = generate_trades(SYMBOLS, lookback=10, adx_min=20, stop_mult=2.0, target_mult=4.0, max_hold_bars=24)

    train_rows = [evaluate(candidate, trades, regimes, start="2023-04-28", end=TRAIN_END) for candidate in CANDIDATES]
    test_rows = [evaluate(candidate, trades, regimes, start=TEST_START, end=TEST_END) for candidate in CANDIDATES]
    baseline_test = next(row for row in test_rows if row["candidate"] == "stable_five_symbol_baseline")

    rows = []
    for train, test in zip(train_rows, test_rows):
        rows.append({
            "candidate": train["candidate"],
            "symbols": train["symbols"],
            "train_monthly_compound": train["monthly_compound"],
            "train_max_drawdown": train["max_drawdown"],
            "train_worst_month": train["worst_month"],
            "train_profit_factor": train["profit_factor"],
            "train_trades": train["trades"],
            "test_monthly_compound": test["monthly_compound"],
            "test_max_drawdown": test["max_drawdown"],
            "test_worst_month": test["worst_month"],
            "test_profit_factor": test["profit_factor"],
            "test_trades": test["trades"],
            "test_monthly_compound_delta": test["monthly_compound"] - baseline_test["monthly_compound"],
            "test_max_drawdown_delta": test["max_drawdown"] - baseline_test["max_drawdown"],
            "test_profit_factor_delta": (test["profit_factor"] or 0) - (baseline_test["profit_factor"] or 0),
            "decision": candidate_decision(train, test, baseline_test),
        })

    write_csv(rows, OUT_DIR / "walk_forward_validation.csv")
    summary = {
        "method": "Candidates are evaluated on 2023-04-28 through 2024-12-31, then compared only on the 2025-01-01 through 2026-04-28 holdout.",
        "rows": rows,
    }
    (OUT_DIR / "walk_forward_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
