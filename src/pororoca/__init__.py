"""Volatility connectedness across the four submarkets of the Brazilian power system."""

from __future__ import annotations

from .analysis import (
    REGIMES,
    annual_summary,
    pairwise_matrix,
    price_separation,
    static_table,
    subperiod_tables,
    zero_share,
)
from .data import SUBMARKETS, build_panel, load_cmo, resource_urls
from .dynamics import RollingDirectional, rolling_directional

__version__ = "0.1.0"

__all__ = [
    "REGIMES",
    "SUBMARKETS",
    "RollingDirectional",
    "__version__",
    "annual_summary",
    "build_panel",
    "load_cmo",
    "pairwise_matrix",
    "price_separation",
    "resource_urls",
    "rolling_directional",
    "static_table",
    "subperiod_tables",
    "zero_share",
]
