"""Static, sub-period and descriptive diagnostics for the Brazilian submarkets."""

from __future__ import annotations

import itertools

import pandas as pd
from connectedness import MHARConfig, SpilloverPipeline, SpilloverResult

from .data import SUBMARKETS

#: Hydrological / market regimes used for the sub-period decomposition.
#: 2023 is kept as its own window on purpose: it is the degenerate surplus year
#: (see README) and excluding it silently would hide why it is unusable.
REGIMES: dict[str, tuple[str, str]] = {
    "2021 water crisis": ("2021-01-01", "2021-12-31"),
    "2022-2023 surplus": ("2022-01-01", "2023-12-31"),
    "2024-2026 segmentation": ("2024-01-01", "2026-12-31"),
}


def static_table(
    panel: pd.DataFrame,
    measure: str = "revar",
    *,
    config: MHARConfig | None = None,
) -> SpilloverResult:
    """Full-sample Diebold-Yilmaz table for one realized measure."""
    result = (
        SpilloverPipeline(panel, measures=(measure,), config=config or MHARConfig(fast=True))
        .compute_returns()
        .compute_realized_measures()
        .force_pit()
        .fit_static()
        .run()
    )
    return result.static[measure]


def subperiod_tables(
    panel: pd.DataFrame,
    measure: str = "revar",
    *,
    regimes: dict[str, tuple[str, str]] | None = None,
    config: MHARConfig | None = None,
) -> dict[str, SpilloverResult]:
    """One Diebold-Yilmaz table per regime."""
    out: dict[str, SpilloverResult] = {}
    for label, (start, end) in (regimes or REGIMES).items():
        chunk = panel.loc[start:end]
        if chunk.empty:
            continue
        out[label] = static_table(chunk, measure, config=config)
    return out


def price_separation(
    panel: pd.DataFrame,
    *,
    threshold: float = 1.0,
    submarkets: tuple[str, ...] = SUBMARKETS,
) -> pd.DataFrame:
    """Share of half-hours (%) in which a pair of submarkets prices apart, by year.

    Two submarkets clear at the same price whenever no transmission constraint
    binds between them, so the complement of this statistic is a direct read of
    how integrated the system is.

    The share is computed **only over half-hours in which at least one of the two
    prices is positive**. Without that condition the measure is dominated by the
    zero-cost hours: in a surplus year both prices are zero and therefore
    trivially "equal", which would report the system as perfectly integrated
    exactly when the price signal carries no information at all.
    """
    years = panel.index.year
    cols: dict[str, pd.Series] = {}
    for a, b in itertools.combinations(submarkets, 2):
        priced = panel[[a, b]].max(axis=1) > 0
        apart = (panel[a].sub(panel[b]).abs() > threshold) & priced
        cols[f"{a}-{b}"] = apart.groupby(years).sum() / priced.groupby(years).sum() * 100
    out = pd.DataFrame(cols)
    out.index.name = "year"
    return out


def pairwise_matrix(
    pairwise: pd.DataFrame,
    *,
    start: str | None = None,
    end: str | None = None,
    submarkets: tuple[str, ...] = SUBMARKETS,
) -> pd.DataFrame:
    """Average rolling pairwise connectedness as a receiver x sender matrix.

    ``pairwise`` is the ``"j->i"`` frame returned by
    :func:`pororoca.dynamics.rolling_directional`. Entry ``(i, j)`` is the share
    of receiver ``i``'s forecast error variance attributed to sender ``j``,
    averaged over the selected windows. The diagonal is left empty.
    """
    mean = pairwise.loc[start:end].mean()
    out = pd.DataFrame(index=list(submarkets), columns=list(submarkets), dtype=float)
    out.index.name = "receiver"
    out.columns.name = "sender"
    for i in submarkets:
        for j in submarkets:
            if i != j:
                out.loc[i, j] = mean[f"{j}->{i}"]
    return out


def zero_share(panel: pd.DataFrame) -> pd.DataFrame:
    """Share of half-hours (%) with a marginal cost of exactly zero, by year.

    These are the hours that the PLD floor censors.
    """
    out = panel.groupby(panel.index.year).apply(lambda g: (g == 0).mean() * 100)
    out.index.name = "year"
    return out


def annual_summary(panel: pd.DataFrame) -> pd.DataFrame:
    """Mean level and mean within-day dispersion of the marginal cost, by year."""
    year = panel.index.year
    level = panel.groupby(year).mean()
    intraday = panel.groupby([year, panel.index.normalize()]).std().groupby(level=0).mean()
    out = pd.concat({"mean R$/MWh": level, "mean intraday sd R$/MWh": intraday}, axis=1)
    out.index.name = "year"
    return out
