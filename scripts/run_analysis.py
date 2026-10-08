#!/usr/bin/env python
"""End-to-end run: download ONS data, estimate connectedness, write results and figures.

python scripts/run_analysis.py --years 2021 2026 --window 365 --jobs 8
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from connectedness import MHARConfig, SpilloverPipeline

from pororoca import (
    annual_summary,
    build_panel,
    load_cmo,
    pairwise_matrix,
    price_separation,
    rolling_directional,
    static_table,
    subperiod_tables,
    zero_share,
)
from pororoca.figures import THEMES, plot_connectedness, plot_separation

ROOT = Path(__file__).resolve().parents[1]
MEASURES = ("revar", "recov_pos", "recov_neg")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", nargs=2, type=int, default=[2021, 2026], metavar=("FROM", "TO"))
    ap.add_argument("--window", type=int, default=365, help="rolling window in days")
    ap.add_argument("--jobs", type=int, default=8, help="parallel windows")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--figures", type=Path, default=ROOT / "figures")
    args = ap.parse_args()

    args.results.mkdir(parents=True, exist_ok=True)
    cfg = MHARConfig(fast=True)

    # ---------------------------------------------------------------- data
    print("[1/6] downloading CMO semi-horario from ONS ...")
    long_df = load_cmo(range(args.years[0], args.years[1] + 1), cache_dir=args.data)
    panel = build_panel(long_df)
    panel.to_parquet(args.data / "panel_cmo.parquet")
    days = panel.index.normalize().nunique()
    print(
        f"      panel: {panel.shape[0]} half-hours, {days} complete days, "
        f"{panel.index.min().date()} to {panel.index.max().date()}"
    )

    # ------------------------------------------------------- descriptives
    print("[2/6] descriptive diagnostics ...")
    sep = price_separation(panel)
    zeros = zero_share(panel)
    levels = annual_summary(panel)
    sep.round(1).to_csv(args.results / "price_separation.csv")
    zeros.round(1).to_csv(args.results / "zero_share.csv")
    levels.round(1).to_csv(args.results / "annual_summary.csv")

    # ------------------------------------------------------- static tables
    print("[3/6] static connectedness tables ...")
    static: dict[str, object] = {}
    for measure in MEASURES:
        res = static_table(panel, measure, config=cfg)
        res.table.round(2).to_csv(args.results / f"static_{measure}.csv")
        static[measure] = res.tsi
        print(f"      {measure:<10} TSI = {res.tsi:.2f}%")

    # ---------------------------------------------------- regime subsamples
    print("[4/6] sub-period tables ...")
    regime_tsi: dict[str, float] = {}
    for label, res in subperiod_tables(panel, "revar", config=cfg).items():
        slug = label.lower().replace(" ", "_").replace("/", "-")
        res.table.round(2).to_csv(args.results / f"regime_{slug}.csv")
        regime_tsi[label] = res.tsi
        print(f"      {label:<26} TSI = {res.tsi:.2f}%")

    # ------------------------------------------------ rolling, directional
    print(f"[5/6] rolling directional connectedness, window={args.window} ...")
    prepared = (
        SpilloverPipeline(panel, measures=("revar",), config=cfg)
        .compute_returns()
        .compute_realized_measures()
        .force_pit()
        .run()
    )
    revar = prepared.transformed["revar"]
    roll = rolling_directional(revar, window=args.window, config=cfg, n_jobs=args.jobs)
    roll.tsi.round(3).to_csv(args.results / "rolling_tsi.csv")
    roll.net.round(3).to_csv(args.results / "rolling_net.csv")
    roll.to_others.round(3).to_csv(args.results / "rolling_to.csv")
    roll.from_others.round(3).to_csv(args.results / "rolling_from.csv")
    roll.pairwise.round(3).to_csv(args.results / "rolling_pairwise.csv")
    pairwise_recent = pairwise_matrix(roll.pairwise, start="2024")
    pairwise_recent.round(2).to_csv(args.results / "pairwise_mean_2024_onwards.csv")
    print(f"      {len(roll.tsi)} windows, alpha = {roll.alpha:.5f}")

    # --------------------------------------------------------------- plots
    print("[6/6] figures ...")
    for theme in THEMES:
        suffix = "" if theme.name == "light" else "-dark"
        plot_connectedness(
            roll.tsi,
            roll.net,
            theme,
            args.figures / f"connectedness{suffix}.png",
            window=args.window,
        )
        plot_separation(sep, theme, args.figures / f"separation{suffix}.png")

    meta = {
        "sample_start": str(panel.index.min()),
        "sample_end": str(panel.index.max()),
        "complete_days": int(days),
        "half_hours": int(panel.shape[0]),
        "window": args.window,
        "alpha": roll.alpha,
        "static_tsi": {k: round(float(v), 2) for k, v in static.items()},
        "regime_tsi": {k: round(float(v), 2) for k, v in regime_tsi.items()},
        "rolling_tsi_last": round(float(roll.tsi.iloc[-1]), 2),
        "rolling_tsi_min": round(float(roll.tsi.min()), 2),
        "rolling_tsi_max": round(float(roll.tsi.max()), 2),
    }
    (args.results / "run_metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("\n" + json.dumps(meta, indent=2))
    pd.set_option("display.width", 200)
    print("\nprice separation (%):\n", sep.round(1).to_string())
    print(
        "\nmean pairwise connectedness 2024+ (rows receive, columns send):\n",
        pairwise_recent.round(1).to_string(),
    )
    print("\nmean net directional 2024+:\n", roll.net.loc["2024":].mean().round(1).to_string())


if __name__ == "__main__":
    main()
