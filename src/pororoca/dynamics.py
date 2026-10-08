"""Rolling-window *directional* connectedness.

The ``connectedness`` package ships ``rolling_spillover``, which fits the
MHAR-LASSO on each window, builds the generalized FEVD, and then keeps only the
total spillover index -- the directional and pairwise entries of the
decomposition are computed and discarded.

A risk desk needs exactly those discarded entries: not "the system is 58%
connected" but "how much of today's shock in SE/CO lands on the Northeast".
This module re-runs the same per-window estimation using the package's public
primitives and returns the full set.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from connectedness import (
    MHARConfig,
    build_lags,
    fit_mhar,
    fit_mhar_fixed_alpha,
    generalized_vd,
    spillover_metrics,
)


@dataclass(frozen=True)
class RollingDirectional:
    """Rolling Diebold-Yilmaz connectedness, directional entries included.

    Attributes
    ----------
    tsi
        Total spillover index (%) indexed by the last date of each window.
    to_others, from_others, net
        Directional contributions (%) per market, one column per market.
    pairwise
        Normalized FEVD entries (%), one column per ordered pair labelled
        ``"j->i"``: the share of market ``i``'s forecast error variance
        attributed to shocks in market ``j``.
    alpha
        The LASSO penalty, held fixed across windows.
    """

    tsi: pd.Series
    to_others: pd.DataFrame
    from_others: pd.DataFrame
    net: pd.DataFrame
    pairwise: pd.DataFrame
    alpha: float


def rolling_directional(
    df: pd.DataFrame,
    window: int = 365,
    config: MHARConfig | None = None,
    *,
    alpha: float | None = None,
    n_jobs: int = 1,
) -> RollingDirectional:
    """Compute rolling TSI together with directional and pairwise connectedness.

    Mirrors ``connectedness.rolling_spillover``: the penalty is selected once on
    the full sample and then held fixed, so window-to-window movement reflects
    the data rather than re-tuned regularization.

    Parameters
    ----------
    df
        Daily realized-measure panel (already PIT-transformed, if desired).
    window
        Window length in days.
    config
        MHAR-LASSO configuration; defaults to the package fast preset.
    alpha
        Fixed penalty. Selected by CV on the full sample when omitted.
    n_jobs
        Parallel windows (requires ``joblib``).
    """
    cfg = config or MHARConfig.fast_preset()
    names = list(df.columns)
    k = len(names)

    if alpha is None:
        xy = build_lags(df, cfg)
        x = xy.drop(columns=df.columns).to_numpy(dtype=np.float64)
        y = xy[df.columns].to_numpy(dtype=np.float64)
        alpha = fit_mhar(x, y, cfg).alpha

    def one_window(start: int) -> tuple[pd.Timestamp, np.ndarray] | None:
        wdf = df.iloc[start : start + window]
        xy = build_lags(wdf, cfg)
        if xy.empty:
            return None
        xw = xy.drop(columns=df.columns).to_numpy(dtype=np.float64)
        yw = xy[df.columns].to_numpy(dtype=np.float64)
        fit = fit_mhar_fixed_alpha(xw, yw, alpha, cfg)
        _, theta_tilde = generalized_vd([np.eye(k), fit.phi1], fit.sigma)
        return xy.index[-1], np.asarray(theta_tilde, dtype=np.float64)

    starts = range(len(df) - window + 1)
    if n_jobs == 1:
        raw = [one_window(s) for s in starts]
    else:
        from joblib import Parallel, delayed

        raw = Parallel(n_jobs=n_jobs)(delayed(one_window)(s) for s in starts)

    results = [r for r in raw if r is not None]
    if not results:
        raise ValueError("no estimable windows; check `window` against the sample length")

    dates = pd.DatetimeIndex([d for d, _ in results], name="date")
    tsi: list[float] = []
    to_rows: list[pd.Series] = []
    from_rows: list[pd.Series] = []
    net_rows: list[pd.Series] = []
    pair_rows: list[list[float]] = []
    pair_labels = [f"{names[j]}->{names[i]}" for i in range(k) for j in range(k) if i != j]

    for _, theta in results:
        t, to_, from_, net_ = spillover_metrics(theta, names)
        tsi.append(t)
        to_rows.append(to_)
        from_rows.append(from_)
        net_rows.append(net_)
        pct = theta * 100.0
        pair_rows.append([pct[i, j] for i in range(k) for j in range(k) if i != j])

    return RollingDirectional(
        tsi=pd.Series(tsi, index=dates, name="tsi"),
        to_others=pd.DataFrame(to_rows, index=dates)[names],
        from_others=pd.DataFrame(from_rows, index=dates)[names],
        net=pd.DataFrame(net_rows, index=dates)[names],
        pairwise=pd.DataFrame(pair_rows, index=dates, columns=pair_labels),
        alpha=float(alpha),
    )
