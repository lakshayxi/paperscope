#!/usr/bin/env python3
"""Regenerate the evaluation figures in docs/assets/ from public aggregate metrics.

Reads only docs/assets/eval_summary_public.json -- a small, redistribution-safe
file containing the aggregate numbers already published in docs/evaluation.md
(rating MAE, decision accuracy, pooled confusion counts). No forum IDs, paper
titles, review text, or individual predictions are read or required.

Usage:
    python scripts/generate_evaluation_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "docs" / "assets" / "eval_summary_public.json"
OUT_DIR = REPO_ROOT / "docs" / "assets"

# Palette (validated categorical pair, light surface) -- see dataviz skill palette.md
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
GENERIC = "#2a78d6"   # categorical slot 1 (blue)
PAPERSCOPE = "#eb6834"  # categorical slot 6 (orange) -- validated CVD-safe pair

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


DELTA_GOOD = "#006300"  # fixed "delta improved" ink role, distinct from the Generic/PaperScope series colors


def _bar_panel(x: float, title: str, direction: str, generic_val: float,
                paperscope_val: float, scale_max: float, value_fmt: str,
                bar_width: float, annotation: str) -> str:
    """One panel: title, direction hint, two labeled horizontal bars, delta annotation."""
    bar_h = 22
    gap = 26
    top = 66
    label_x = x + 4
    label_offset = 8

    def bar(y: float, value: float, color: str, label: str) -> str:
        w = max(2.0, (value / scale_max) * bar_width)
        return f"""
    <text x="{label_x}" y="{y - label_offset}" font-family="{FONT}" font-size="12" fill="{INK_SECONDARY}">{label}</text>
    <rect x="{label_x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="{GRIDLINE}" rx="3"/>
    <rect x="{label_x}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{color}" rx="3"/>
    <text x="{label_x + bar_width + 10}" y="{y + bar_h - 6}" font-family="{FONT}" font-size="13" font-weight="600" fill="{INK_PRIMARY}">{value_fmt.format(value)}</text>"""

    bar2_y = top + bar_h + gap
    annotation_y = bar2_y + bar_h + 24
    annotation_x = label_x + bar_width / 2

    return f"""
  <g>
    <text x="{label_x}" y="24" font-family="{FONT}" font-size="14" font-weight="700" fill="{INK_PRIMARY}">{title}</text>
    <text x="{label_x}" y="42" font-family="{FONT}" font-size="11.5" fill="{INK_MUTED}">{direction}</text>
    {bar(top, generic_val, GENERIC, "Generic")}
    {bar(bar2_y, paperscope_val, PAPERSCOPE, "PaperScope")}
    <text x="{annotation_x}" y="{annotation_y}" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="700" fill="{DELTA_GOOD}">{annotation}</text>
  </g>"""


def build_figure1(data: dict) -> str:
    rating = data["rating"]
    decision = data["decision"]

    panel_w = 300
    width = panel_w * 3
    height = 190

    p1 = _bar_panel(
        x=0, title="Rating MAE (lower is better)", direction="50 rating-eligible forums",
        generic_val=rating["generic_mae"], paperscope_val=rating["paperscope_mae"],
        scale_max=1.6, value_fmt="{:.2f}", bar_width=170, annotation="−21.8%",
    )
    p2 = _bar_panel(
        x=panel_w, title="Decision accuracy (higher is better)", direction="35 resolved decisions",
        generic_val=decision["generic_accuracy_pct"], paperscope_val=decision["paperscope_accuracy_pct"],
        scale_max=100, value_fmt="{:.1f}%", bar_width=170, annotation="+14.3 pp",
    )
    p3 = _bar_panel(
        x=panel_w * 2, title="False accepts (fewer is better)", direction="35 resolved decisions",
        generic_val=decision["generic_confusion"]["false_accept"],
        paperscope_val=decision["paperscope_confusion"]["false_accept"],
        scale_max=10, value_fmt="{:.0f}", bar_width=170, annotation="−7",
    )

    # Panel dividers only *between* panels -- never at the outer canvas edge.
    dividers = "".join(
        f'\n  <line x1="{panel_w * i}" y1="16" x2="{panel_w * i}" y2="{height - 20}" '
        f'stroke="{GRIDLINE}" stroke-width="1"/>'
        for i in (1, 2)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Generic versus PaperScope on rating MAE, decision accuracy, and false accepts">
  <rect x="0" y="0" width="{width}" height="{height}" fill="{SURFACE}"/>
  {p1}
  {p2}
  {p3}{dividers}
</svg>
"""


def _blue_for_count(count: int, max_count: int) -> str:
    """Sequential blue ramp step, keyed to a shared count scale across both matrices."""
    steps = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]
    frac = 0 if max_count == 0 else count / max_count
    idx = min(len(steps) - 1, int(frac * (len(steps) - 1) + 0.5))
    return steps[idx]


def _orange_alpha_for_count(count: int, max_count: int) -> str:
    """Sequential orange intensity (alpha over the surface), keyed to the same shared scale."""
    frac = 0 if max_count == 0 else count / max_count
    alpha = 0.12 + 0.78 * frac
    return f"rgba(235, 104, 52, {alpha:.2f})"


CONFUSION_ABBR = {
    "true_accept": "TP",
    "false_reject": "FN",
    "false_accept": "FP",
    "true_reject": "TN",
}


def _confusion_matrix(x: float, title: str, confusion: dict, max_count: int, color_fn) -> str:
    cell = 78
    grid_x = x + 108
    grid_y = 56
    labels = [
        ("true_accept", 0, 0),
        ("false_reject", 1, 0),
        ("false_accept", 0, 1),
        ("true_reject", 1, 1),
    ]
    cells = []
    for key, col, row in labels:
        count = confusion[key]
        cx = grid_x + col * cell
        cy = grid_y + row * cell
        fill = color_fn(count, max_count)
        center_x = cx + (cell - 2) / 2
        center_y = cy + (cell - 2) / 2
        cells.append(f"""
    <rect x="{cx}" y="{cy}" width="{cell - 2}" height="{cell - 2}" fill="{fill}" stroke="{GRIDLINE}" stroke-width="1" rx="4"/>
    <text x="{center_x}" y="{center_y}" text-anchor="middle" font-family="{FONT}" font-size="20" font-weight="700" fill="{INK_PRIMARY}">{count}</text>
    <text x="{center_x}" y="{center_y + 18}" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="600" fill="{INK_PRIMARY}" fill-opacity="0.6">{CONFUSION_ABBR[key]}</text>""")

    return f"""
  <g>
    <text x="{x}" y="20" font-family="{FONT}" font-size="14" font-weight="700" fill="{INK_PRIMARY}">{title}</text>
    <text x="{grid_x + cell / 2}" y="{grid_y - 8}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{INK_MUTED}">Pred. accept</text>
    <text x="{grid_x + cell + cell / 2}" y="{grid_y - 8}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{INK_MUTED}">Pred. reject</text>
    <text x="{x}" y="{grid_y + cell / 2 + 4}" font-family="{FONT}" font-size="11" fill="{INK_MUTED}">Actual accept</text>
    <text x="{x}" y="{grid_y + cell + cell / 2 + 4}" font-family="{FONT}" font-size="11" fill="{INK_MUTED}">Actual reject</text>
    {"".join(cells)}
  </g>"""


def build_figure2(data: dict) -> str:
    decision = data["decision"]
    generic = decision["generic_confusion"]
    paperscope = decision["paperscope_confusion"]
    max_count = max(list(generic.values()) + list(paperscope.values()))

    width, height = 640, 254
    left = _confusion_matrix(24, "Generic", generic, max_count, _blue_for_count)
    right = _confusion_matrix(24 + 320, "PaperScope", paperscope, max_count, _orange_alpha_for_count)

    caption_y = height - 24
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Confusion matrices for Generic and PaperScope decision predictions, pooled across 35 resolved ICLR 2024 forums">
  <rect x="0" y="0" width="{width}" height="{height}" fill="{SURFACE}"/>
  {left}
  {right}
  <line x1="{24 + 320 - 24}" y1="16" x2="{24 + 320 - 24}" y2="{height - 64}" stroke="{GRIDLINE}" stroke-width="1"/>
  <text x="24" y="{caption_y}" font-family="{FONT}" font-size="11" fill="{INK_MUTED}">Pooled across 35 resolved ICLR 2024 forums. Darker cell = higher count on a shared 0–16 scale.</text>
</svg>
"""


def main() -> None:
    data = json.loads(DATA_PATH.read_text())

    fig1_path = OUT_DIR / "fig1_headline_impact.svg"
    fig2_path = OUT_DIR / "fig2_confusion_matrices.svg"

    fig1_path.write_text(build_figure1(data))
    fig2_path.write_text(build_figure2(data))

    print(f"wrote {fig1_path.relative_to(REPO_ROOT)}")
    print(f"wrote {fig2_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
