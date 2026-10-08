"""Figures for the README, rendered in a light and a dark variant.

Colour assignment follows one rule: a hue belongs to a *submarket*, not to a
rank, so SE/CO is the same blue in every panel. The dark variant is a separate
set of steps from the same ramps rather than an inverted copy of the light one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from .data import SUBMARKET_LABELS, SUBMARKETS


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    ink: str
    ink_secondary: str
    ink_muted: str
    grid: str
    axis: str
    series: dict[str, str]
    ramp: tuple[str, ...]


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    ink="#0b0b0b",
    ink_secondary="#52514e",
    ink_muted="#898781",
    grid="#e1e0d9",
    axis="#c3c2b7",
    series={"SE": "#2a78d6", "S": "#eb6834", "NE": "#1baf7a", "N": "#eda100"},
    ramp=("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"),
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    ink="#ffffff",
    ink_secondary="#c3c2b7",
    ink_muted="#898781",
    grid="#2c2c2a",
    axis="#383835",
    series={"SE": "#3987e5", "S": "#d95926", "NE": "#199e70", "N": "#c98500"},
    ramp=("#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"),
)

THEMES: tuple[Theme, ...] = (LIGHT, DARK)


def _style(ax: plt.Axes, theme: Theme) -> None:
    ax.set_facecolor(theme.surface)
    ax.grid(True, axis="y", color=theme.grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme.axis)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=theme.ink_muted, labelsize=9, length=3, width=0.8)


def plot_connectedness(
    tsi: pd.Series,
    net: pd.DataFrame,
    theme: Theme,
    out_path: Path,
    *,
    window: int,
) -> Path:
    """Rolling total index and rolling net directional connectedness.

    Two stacked panels rather than one chart with two y-axes: the total index is
    a share of forecast error variance and the net measures are differences in
    percentage points, so they do not belong on a shared scale.
    """
    mpl.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 160})
    fig, (ax_t, ax_n) = plt.subplots(
        2, 1, figsize=(9.0, 6.4), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]}
    )
    fig.patch.set_facecolor(theme.surface)

    # --- Panel 1: total spillover index (one series, so no legend; title names it)
    _style(ax_t, theme)
    ax_t.plot(tsi.index, tsi.to_numpy(), color=theme.series["SE"], linewidth=2.0, zorder=3)
    ax_t.set_ylabel("% of forecast error variance", color=theme.ink_secondary, fontsize=9)
    ax_t.set_title(
        f"Total volatility connectedness, Brazilian submarkets ({window}-day window)",
        color=theme.ink,
        fontsize=12,
        fontweight="bold",
        loc="left",
        pad=10,
    )
    last_t = tsi.iloc[-1]
    ax_t.annotate(
        f"{last_t:.0f}%",
        xy=(tsi.index[-1], last_t),
        xytext=(6, 0),
        textcoords="offset points",
        color=theme.ink_secondary,
        fontsize=9,
        va="center",
    )

    # --- Panel 2: net directional, one line per submarket, all direct-labelled
    _style(ax_n, theme)
    ax_n.axhline(0.0, color=theme.axis, linewidth=1.0, zorder=1)
    for code in SUBMARKETS:
        if code not in net.columns:
            continue
        series = net[code]
        ax_n.plot(
            series.index,
            series.to_numpy(),
            color=theme.series[code],
            linewidth=2.0,
            label=SUBMARKET_LABELS[code],
            zorder=3,
        )
        ax_n.annotate(
            SUBMARKET_LABELS[code],
            xy=(series.index[-1], series.iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            color=theme.ink_secondary,
            fontsize=8.5,
            va="center",
        )
    ax_n.set_ylabel("net: transmitted − received (pp)", color=theme.ink_secondary, fontsize=9)
    ax_n.set_title(
        "Net directional connectedness — above zero transmits, below zero receives",
        color=theme.ink_secondary,
        fontsize=10,
        loc="left",
        pad=8,
    )
    leg = ax_n.legend(
        loc="upper left",
        ncols=4,
        frameon=False,
        fontsize=9,
        labelcolor=theme.ink_secondary,
        handlelength=1.6,
        columnspacing=1.4,
    )
    for text in leg.get_texts():
        text.set_color(theme.ink_secondary)

    fig.subplots_adjust(right=0.90)
    fig.tight_layout(rect=(0, 0, 0.93, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=theme.surface, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_separation(separation: pd.DataFrame, theme: Theme, out_path: Path) -> Path:
    """Heatmap of the share of half-hours in which each pair of submarkets prices apart."""
    mpl.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 160})
    cmap = LinearSegmentedColormap.from_list(f"ramp_{theme.name}", list(theme.ramp))
    data = separation.T  # pairs on y, years on x

    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    fig.patch.set_facecolor(theme.surface)
    ax.set_facecolor(theme.surface)
    mesh = ax.imshow(data.to_numpy(), cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(data.columns)), [str(c) for c in data.columns])
    ax.set_yticks(range(len(data.index)), list(data.index))
    ax.tick_params(colors=theme.ink_muted, labelsize=9, length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(data.columns))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(data.index))], minor=True)
    ax.grid(which="minor", color=theme.surface, linewidth=2.0)
    ax.tick_params(which="minor", length=0)

    # Values on the cells: the colour carries magnitude, the label carries the number.
    norm = mesh.norm
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data.to_numpy()[i, j]
            shade = norm(value)
            dark_cell = shade > 0.55 if theme.name == "light" else shade < 0.45
            ax.text(
                j,
                i,
                f"{value:.0f}",
                ha="center",
                va="center",
                fontsize=9,
                color=theme.surface if dark_cell else theme.ink,
            )

    ax.set_title(
        "Share of half-hours priced apart (> R$1/MWh), among hours with a positive price",
        color=theme.ink,
        fontsize=11,
        fontweight="bold",
        loc="left",
        pad=10,
    )
    bar = fig.colorbar(mesh, ax=ax, fraction=0.025, pad=0.02)
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=theme.ink_muted, labelsize=8, length=0)
    bar.set_label("% of half-hours", color=theme.ink_secondary, fontsize=9)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=theme.surface, bbox_inches="tight")
    plt.close(fig)
    return out_path
