"""Access to ONS open data: half-hourly marginal operating cost (CMO) by submarket.

The Brazilian spot price (PLD) is a censored transform of the CMO shadow price
produced by the DESSEM model. This module pulls the *uncensored* CMO series that
ONS publishes, which is the input the connectedness estimator actually needs.
See the README section "Why CMO and not PLD" for the argument.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

ONS_PACKAGE_SHOW = "https://dados.ons.org.br/api/3/action/package_show"

#: Submarkets in the order used throughout the analysis (SE/CO, South, NE, North).
SUBMARKETS: tuple[str, ...] = ("SE", "S", "NE", "N")

#: Human-readable labels.
SUBMARKET_LABELS: dict[str, str] = {
    "SE": "SE/CO",
    "S": "Sul",
    "NE": "Nordeste",
    "N": "Norte",
}

_UA = "pororoca/0.1 (research; +https://github.com/franrolotti)"


def resource_urls(dataset: str = "cmo-semi-horario", fmt: str = "PARQUET") -> dict[str, str]:
    """Map resource name to download URL for an ONS open-data dataset.

    Parameters
    ----------
    dataset
        CKAN dataset slug, e.g. ``"cmo-semi-horario"``, ``"intercambio-nacional"``,
        ``"ena-diario-por-subsistema"``.
    fmt
        Resource format to keep (``"PARQUET"``, ``"CSV"``, ``"XLSX"``).
    """
    req = urllib.request.Request(  # noqa: S310 - fixed https host
        f"{ONS_PACKAGE_SHOW}?id={dataset}", headers={"User-Agent": _UA}
    )
    with urllib.request.urlopen(req, timeout=60) as fh:  # noqa: S310
        payload = json.load(fh)
    resources = payload["result"]["resources"]
    return {r["name"]: r["url"] for r in resources if r.get("format") == fmt}


def _download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as fh, dest.open("wb") as out:  # noqa: S310
        out.write(fh.read())
    return dest


def load_cmo(
    years: range | list[int],
    cache_dir: str | Path = "data",
    *,
    dataset: str = "cmo-semi-horario",
) -> pd.DataFrame:
    """Download (with on-disk cache) and concatenate half-hourly CMO by submarket.

    Returns a long frame with columns ``id_subsistema``, ``din_instante``, ``val_cmo``.
    ONS ships some years with the value column typed as string, so it is coerced here.
    """
    cache = Path(cache_dir)
    urls = resource_urls(dataset)
    frames: list[pd.DataFrame] = []
    for year in years:
        key = next((k for k in urls if k.endswith(str(year))), None)
        if key is None:
            continue
        path = _download(urls[key], cache / f"CMO_SEMIHORARIO_{year}.parquet")
        frames.append(pd.read_parquet(path))
    if not frames:
        raise ValueError(f"no CMO resources found for years {list(years)}")
    df = pd.concat(frames, ignore_index=True)
    df["val_cmo"] = pd.to_numeric(df["val_cmo"], errors="coerce")
    df["din_instante"] = pd.to_datetime(df["din_instante"])
    return df


def build_panel(
    long_df: pd.DataFrame,
    *,
    submarkets: tuple[str, ...] = SUBMARKETS,
    complete_days_only: bool = True,
    obs_per_day: int = 48,
) -> pd.DataFrame:
    """Pivot long CMO data into the wide intraday panel the estimator expects.

    Realized (semi)covariance is a within-day sum, so days with missing
    half-hours would be mechanically less volatile than complete ones. With
    ``complete_days_only`` only days carrying all ``obs_per_day`` observations in
    every submarket are kept.
    """
    wide = (
        long_df.pivot_table(
            index="din_instante", columns="id_subsistema", values="val_cmo", aggfunc="mean"
        )
        .sort_index()
        .loc[:, list(submarkets)]
        .dropna(how="any")
    )
    if complete_days_only:
        counts = wide.groupby(wide.index.normalize()).size()
        keep = counts[counts == obs_per_day].index
        wide = wide[pd.Index(wide.index.normalize()).isin(keep)]
    wide.columns.name = None
    return wide
