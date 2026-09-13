import json
from pathlib import Path

from portfolio_swing_backtest import write_csv
from risk_research_backtest import SYMBOLS, btc_daily_regime, generate_trades, portfolio


OUT_DIR = Path("./risk_research_results")
REDUCE_LEVELS = [-0.04, -0.06, -0.08, -0.10]
STOP_LEVELS = [-0.08, -0.10, -0.12, -0.15]

PROFILES = [
    {
        "profile": "balanced",
        "baseline_reduce_at": -0.06,
        "baseline_stop_at": -0.10,
        "risk_pct": 0.03,
        "max_positions": 2,
        "max_same_side": 1,
        "max_position_fraction": 1.5,
        "max_total_exposure": 3.0,
        "regime_filter": "none",
        "vol_filter": "none",
        "min_monthly_compound": 0.05,
        "min_max_drawdown": -0.30,
        "min_worst_month": -0.15,
        "min_profit_factor": 1.35,
    },
    {
        "profile": "stable",
        "baseline_reduce_at": -0.08,
        "baseline_stop_at": -0.12,
        "risk_pct": 0.025,
        "max_positions": 2,
        "max_same_side": 1,
        "max_position_fraction": 1.5,
        "max_total_exposure": 3.0,
        "regime_filter": "none",
        "vol_filter": "skip_extreme",
        "min_monthly_compound": 0.04,
        "min_max_drawdown": -0.22,
        "min_worst_month": -0.14,
        "min_profit_factor": 1.35,
    },
]


def candidate_configs(profile):
    for reduce_at in REDUCE_LEVELS:
        for stop_at in STOP_LEVELS:
            if reduce_at <= stop_at:
                continue
            cfg = {
                "risk_pct": profile["risk_pct"],
                "max_positions": profile["max_positions"],
                "max_same_side": profile["max_same_side"],
                "max_position_fraction": profile["max_position_fraction"],
                "max_total_exposure": profile["max_total_exposure"],
                "regime_filter": profile["regime_filter"],
                "vol_filter": profile["vol_filter"],
                "monthly_reduce_at": reduce_at,
                "monthly_stop_at": stop_at,
            }
            yield cfg


def passes_gates(row, profile):
    return (
        row["monthly_compound"] >= profile["min_monthly_compound"]
        and row["max_drawdown"] >= profile["min_max_drawdown"]
        and row["worst_month"] >= profile["min_worst_month"]
        and (row["profit_factor"] or 0) >= profile["min_profit_factor"]
        and row["trades"] >= 100
    )


def improvement_notes(row, baseline):
    notes = []
    if row["worst_month"] > baseline["worst_month"]:
        notes.append("better_worst_month")
    if row["max_drawdown"] > baseline["max_drawdown"]:
        notes.append("better_max_drawdown")
    if row["monthly_compound"] > baseline["monthly_compound"]:
        notes.append("better_monthly_compound")
    if (row["profit_factor"] or 0) > (baseline["profit_factor"] or 0):
        notes.append("better_profit_factor")
    return ",".join(notes) if notes else "no_clear_improvement"


def candidate_status(row):
    if row["is_current_baseline"]:
        return "baseline"
    if not row["accepted"]:
        return "rejected"
    if row["improvement_notes"] == "no_clear_improvement":
        return "rejected"
    if row["monthly_compound_delta"] < -0.002:
        return "needs_more_testing"
    if row["max_drawdown_delta"] < -0.005:
        return "needs_more_testing"
    if row["worst_month_delta"] < -0.005:
        return "needs_more_testing"
    if row["profit_factor_delta"] < -0.01:
        return "needs_more_testing"
    return "accepted_candidate"


def score(row):
    status_rank = {
        "accepted_candidate": 3,
        "baseline": 2,
        "needs_more_testing": 1,
        "rejected": 0,
    }
    return (
        status_rank[row["candidate_status"]],
        row["worst_month"],
        row["max_drawdown"],
        row["monthly_compound"],
        row["profit_factor"] or 0,
        row["trades"],
    )


def run_profile(profile, trades, regimes):
    rows = []
    baseline = None
    for cfg in candidate_configs(profile):
        summary, _closed = portfolio(trades, cfg, regimes)
        row = dict(summary)
        row["profile"] = profile["profile"]
        row["accepted"] = passes_gates(row, profile)
        row["is_current_baseline"] = (
            cfg["monthly_reduce_at"] == profile["baseline_reduce_at"]
            and cfg["monthly_stop_at"] == profile["baseline_stop_at"]
        )
        rows.append(row)
        if row["is_current_baseline"]:
            baseline = row

    if baseline is None:
        raise RuntimeError(f"Missing baseline row for {profile['profile']}")

    for row in rows:
        row["improvement_notes"] = improvement_notes(row, baseline)
        row["monthly_compound_delta"] = row["monthly_compound"] - baseline["monthly_compound"]
        row["max_drawdown_delta"] = row["max_drawdown"] - baseline["max_drawdown"]
        row["worst_month_delta"] = row["worst_month"] - baseline["worst_month"]
        row["profit_factor_delta"] = (row["profit_factor"] or 0) - (baseline["profit_factor"] or 0)
        row["candidate_status"] = candidate_status(row)

    ranked = sorted(rows, key=score, reverse=True)
    best = ranked[0]
    decision = best["candidate_status"]
    return {
        "profile": profile["profile"],
        "decision": decision,
        "baseline": baseline,
        "best_candidate": best,
        "top_candidates": ranked[:5],
    }, rows


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    regimes = btc_daily_regime()
    trades = generate_trades(SYMBOLS, lookback=10, adx_min=20, stop_mult=2.0, target_mult=4.0, max_hold_bars=24)

    all_rows = []
    profile_summaries = []
    for profile in PROFILES:
        profile_summary, rows = run_profile(profile, trades, regimes)
        profile_summaries.append(profile_summary)
        all_rows.extend(rows)

    all_rows = sorted(all_rows, key=lambda row: (row["profile"], score(row)), reverse=True)
    write_csv(all_rows, OUT_DIR / "monthly_loss_defense_grid.csv")
    (OUT_DIR / "monthly_loss_defense_summary.json").write_text(
        json.dumps(profile_summaries, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(profile_summaries, indent=2))


if __name__ == "__main__":
    main()
