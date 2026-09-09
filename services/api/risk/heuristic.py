"""Weighted physical risk index - the fallback when a trained model
isn't available. No training, works immediately. See docs/TRAINING.md #6.

    susceptibility = 0.30*norm(slope_deg) + 0.20*norm(-curv_prof)
                   + 0.20*is_cut_slope + 0.15*lithology_weight
                   + 0.10*norm(1-forest_frac) + 0.05*norm(ls_factor)

lithology_weight is not available yet (needs the GSI export, see
ml/sampling.py's same disclosure) - when it is None, its 0.15 weight is
redistributed across the other five terms so they still sum to 1.0,
rather than silently depressing every score by 15% and shifting the
band thresholds underneath the map.

Landslide inventories for this district (docs/TRAINING.md #3) give too
few positives to train a model that survives spatial cross-validation
(services/api/ml/sampling.py), so this heuristic - not risk/model.py -
is the primary risk surface. Every score it produces carries
provenance="index".

Returns the same shape as risk/model.py's predict(), plus per-term
contributions so the cell detail panel works identically whichever
one is behind /risk/cell/{id}.
"""

from __future__ import annotations

import numpy as np

_WEIGHTS = {
    "slope": 0.30,
    "curv_prof": 0.20,
    "is_cut_slope": 0.20,
    "lithology": 0.15,
    "forest_frac": 0.10,
    "ls_factor": 0.05,
}


def _minmax_norm(values: np.ndarray, low_pct: float = 5.0, high_pct: float = 95.0) -> np.ndarray:
    """Min-max normalisation against the [low_pct, high_pct] percentile
    range rather than the raw min/max. A small number of extreme
    outliers (a few near-vertical cut faces in an otherwise moderate
    terrain) would otherwise compress the entire rest of the field
    toward the same near-0-or-1 value under plain min-max - clipping to
    percentiles keeps the majority's real spread while still mapping
    genuine outliers to (clipped) 0 or 1.
    """
    values = np.asarray(values, dtype=float)
    vmin, vmax = np.nanpercentile(values, low_pct), np.nanpercentile(values, high_pct)
    if vmax - vmin < 1e-12:
        return np.zeros_like(values)  # constant field: no relative risk signal
    return np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)


def _weights_for(lithology_weight: np.ndarray | None) -> tuple[dict[str, float], bool]:
    has_lithology = lithology_weight is not None and not np.all(np.isnan(np.asarray(lithology_weight, dtype=float)))
    if has_lithology:
        return dict(_WEIGHTS), True

    remaining = {k: v for k, v in _WEIGHTS.items() if k != "lithology"}
    total = sum(remaining.values())
    renormalised = {k: v / total for k, v in remaining.items()}
    print(f"[risk.heuristic] lithology not available - renormalised the remaining "
          f"{len(remaining)} weights to sum to 1.0 (dropped lithology's {_WEIGHTS['lithology']:.2f} "
          f"rather than leaving every score depressed by it)")
    return renormalised, False


def compute_heuristic_risk(
    slope_deg: np.ndarray,
    curv_prof: np.ndarray,
    is_cut_slope: np.ndarray,
    forest_frac: np.ndarray,
    ls_factor: np.ndarray,
    lithology_weight: np.ndarray | None = None,
    weights: dict[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    w, has_lithology = (dict(weights), True) if weights is not None else _weights_for(lithology_weight)

    contributions = {
        "slope": w["slope"] * _minmax_norm(slope_deg),
        # concave curvature concentrates flow and saturation - higher risk
        "curv_prof": w["curv_prof"] * _minmax_norm(-np.asarray(curv_prof, dtype=float)),
        "is_cut_slope": w["is_cut_slope"] * np.asarray(is_cut_slope, dtype=float),
        "forest_frac": w["forest_frac"] * _minmax_norm(1.0 - np.asarray(forest_frac, dtype=float)),
        "ls_factor": w["ls_factor"] * _minmax_norm(ls_factor),
    }
    if has_lithology:
        contributions["lithology"] = w["lithology"] * _minmax_norm(lithology_weight)

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
