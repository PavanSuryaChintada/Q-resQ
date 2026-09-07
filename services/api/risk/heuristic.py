"""Weighted physical risk index - the fallback when a trained model
isn't available. No training, works immediately. See BUILD_SPEC.md.

    risk = 0.40*norm(1-hand) + 0.30*norm(rain_72h) + 0.15*norm(1-slope)
         + 0.10*norm(1-dist_stream) + 0.05*drainage_penalty

Min-max normalisation is invariant to an additive constant, so
norm(1-hand) and 1-norm(hand) are numerically identical - this
implementation uses the latter form.

These are still the flood-build's default weights, not yet retrained
for landslide susceptibility - docs/TRAINING.md #6 is where the real
NER heuristic (slope/curvature/cut-slope/lithology-led) replaces this
formula. Kept as a single, honestly-labelled placeholder path rather
than a multi-hazard switch, since NER has one dominant hazard.

Returns the same shape as risk/model.py's predict(), plus per-term
contributions so the cell detail panel works identically whichever
one is behind /risk/cell/{id}.
"""

from __future__ import annotations

import numpy as np

_WEIGHTS = {"hand": 0.40, "rain_72h": 0.30, "slope": 0.15, "dist_stream": 0.10, "drainage": 0.05}


def _minmax_norm(values: np.ndarray, low_pct: float = 5.0, high_pct: float = 95.0) -> np.ndarray:
    """Min-max normalisation against the [low_pct, high_pct] percentile
    range rather than the raw min/max. A small number of extreme
    outliers (a few hilly cells in an otherwise low-lying floodplain)
    would otherwise compress the entire rest of the field toward the
    same near-0-or-1 value under plain min-max - clipping to
    percentiles keeps the majority's real spread while still mapping
    genuine outliers to (clipped) 0 or 1.
    """
    values = np.asarray(values, dtype=float)
    vmin, vmax = np.nanpercentile(values, low_pct), np.nanpercentile(values, high_pct)
    if vmax - vmin < 1e-12:
        return np.zeros_like(values)  # constant field: no relative risk signal
    return np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)


def compute_heuristic_risk(
    hand: np.ndarray,
    rain_72h: np.ndarray,
    slope_deg: np.ndarray,
    dist_stream_m: np.ndarray,
    drainage_penalty: np.ndarray,
    weights: dict[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    w = weights or _WEIGHTS
    contributions = {
        "hand": w["hand"] * (1.0 - _minmax_norm(hand)),
        "rain_72h": w["rain_72h"] * _minmax_norm(rain_72h),
        "slope": w["slope"] * (1.0 - _minmax_norm(slope_deg)),
        "dist_stream": w["dist_stream"] * (1.0 - _minmax_norm(dist_stream_m)),
        "drainage": w["drainage"] * np.asarray(drainage_penalty, dtype=float),
    }
    risk_score = sum(contributions.values())
    return risk_score, contributions


def band(score: float) -> int:
    """0 normal · 1 watch · 2 alert · 3 warning · 4 severe (IMD ladder)."""
    if score < 0.2:
        return 0
    if score < 0.4:
        return 1
    if score < 0.6:
        return 2
    if score < 0.8:
        return 3
    return 4
