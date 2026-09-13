"""Test whether smaller crypto universes improve robustness without changing live defaults."""

import itertools
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from portfolio_swing_backtest import write_csv
from risk_research_backtest import SYMBOLS, btc_daily_regime, portfolio, generate_trades


OUT_DIR = Path("./risk_research_results")
YEARS = (2023, 2024, 2025, 2026)
PROFILES = (
    {
        "profile": "balanced",
        "risk_pct": 0.03,
        "vol_filter": "none",
        "monthly_reduce_at": -0.06,
        "monthly_stop_at": -0.10,
        "min_monthly_compound": 0.05,
        "min_max_drawdown": -0.30,
        "min_worst_month": -0.15,
        "min_profit_factor": 1.35,
    },
    {
        "profile": "stable",
        "risk_pct": 0.025,
        "vol_filter": "skip_extreme",
        "monthly_reduce_at": -0.08,
        "monthly_stop_at": -0.12,
        "min_monthly_compound": 0.04,
        "min_max_drawdown": -0.22,
        "min_worst_month": -0.14,
        "min_profit_factor": 1.35,
    },
)


def config(profile):
    return {
        "risk_pct": profile["risk_pct"],
        "max_positions": 2,
        "max_same_side": 1,
        "max_position_fraction": 1.5,
        "max_total_exposure": 3.0,
        "regime_filter": "none",
        "vol_filter": profile["vol_filter"],
        "monthly_reduce_at": profile["monthly_reduce_at"],
        "monthly_stop_at": profile["monthly_stop_at"],
    }


def year_of(trade):
    return datetime.fromtimestamp(trade["entry_ts"] / 1000, tz=timezone.utc).year


def symbol_rows(closed):
    grouped = defaultdict(list)
    for row in closed:
        grouped[row["symbol"]].append(float(row["equity_return"]))
    rows = []
    for symbol, returns in grouped.items():
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value <= 0]
        rows.append({
            "symbol": symbol,
            "trades": len(returns),
            "return_contribution": sum(returns),
            "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        })
    return sorted(rows, key=lambda row: row["return_contribution"], reverse=True)


def passes_gates(row, profile):
    return (
        row["monthly_compound"] >= profile["min_monthly_compound"]
        and row["max_drawdown"] >= profile["min_max_drawdown"]
        and row["worst_month"] >= profile["min_worst_month"]
        and (row["profit_factor"] or 0) >= profile["min_profit_factor"]
        and row["trades"] >= 100
    )


def evaluate_subset(subset, profile, all_trades, regimes):
    selected = [trade for trade in all_trades if trade["symbol"] in subset]
    summary, closed = portfolio(selected, config(profile), regimes)
    row = dict(summary)
    row.update({
        "profile": profile["profile"],
        "symbols": ",".join(subset),
        "symbol_count": len(subset),
        "accepted_gates": passes_gates(row, profile),
    })
    yearly = []
    for year in YEARS:
        year_trades = [trade for trade in selected if year_of(trade) == year]
        if not year_trades:
            continue
        year_summary, _ = portfolio(year_trades, config(profile), regimes)
        yearly.append({"year": year, **year_summary})
    row["positive_years"] = sum(1 for value in yearly if value["total_return"] > 0)
    row["tested_years"] = len(yearly)
    row["worst_year_return"] = min((value["total_return"] for value in yearly), default=0.0)
    return row, closed, yearly


def status(row, baseline):
    if row["symbols"] == baseline["symbols"]:
        return "baseline"
    improved = (
        row["max_drawdown"] > baseline["max_drawdown"]
        or (row["profit_factor"] or 0) > (baseline["profit_factor"] or 0)
    )
    no_major_trade_loss = row["trades"] >= baseline["trades"] * 0.70
    robust = row["positive_years"] >= max(2, row["tested_years"] - 1)
    if row["accepted_gates"] and improved and no_major_trade_loss and robust:
        return "needs_more_testing"
    return "rejected"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    regimes = btc_daily_regime()
    all_trades = generate_trades(SYMBOLS, lookback=10, adx_min=20, stop_mult=2.0, target_mult=4.0, max_hold_bars=24)
    all_rows = []
    all_yearly = []
    profile_summaries = []

    for profile in PROFILES:
        evaluations = []
        for size in (3, 4, 5):
            for subset in itertools.combinations(SYMBOLS, size):
                row, closed, yearly = evaluate_subset(subset, profile, all_trades, regimes)
                evaluations.append((row, closed, yearly))

        baseline = next(row for row, _, _ in evaluations if row["symbol_count"] == len(SYMBOLS))
        for row, _, _ in evaluations:
            row["monthly_compound_delta"] = row["monthly_compound"] - baseline["monthly_compound"]
            row["max_drawdown_delta"] = row["max_drawdown"] - baseline["max_drawdown"]
            row["profit_factor_delta"] = (row["profit_factor"] or 0) - (baseline["profit_factor"] or 0)
            row["candidate_status"] = status(row, baseline)
            all_rows.append(row)

        baseline_closed = next(closed for row, closed, _ in evaluations if row["symbols"] == baseline["symbols"])
        contributions = symbol_rows(baseline_closed)
        for contribution in contributions:
            contribution["profile"] = profile["profile"]
        write_csv(contributions, OUT_DIR / f"symbol_contribution_{profile['profile']}.csv")

        for row, _, yearly in evaluations:
            for year in yearly:
                all_yearly.append({"profile": profile["profile"], "symbols": row["symbols"], **year})

        candidates = [row for row, _, _ in evaluations if row["candidate_status"] == "needs_more_testing"]
        profile_summaries.append({
            "profile": profile["profile"],
            "baseline": baseline,
            "symbol_contribution": contributions,
            "candidates": candidates,
            "decision": "keep_current_five_symbol_universe" if not candidates else "validate_candidates_year_by_year",
        })

    write_csv(all_rows, OUT_DIR / "symbol_pruning_grid.csv")
    write_csv(all_yearly, OUT_DIR / "symbol_pruning_yearly.csv")
    (OUT_DIR / "symbol_pruning_summary.json").write_text(json.dumps(profile_summaries, indent=2), encoding="utf-8")
    print(json.dumps(profile_summaries, indent=2))


if __name__ == "__main__":
    main()
