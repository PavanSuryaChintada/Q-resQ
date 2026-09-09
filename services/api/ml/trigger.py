"""Rainfall trigger index - a physical index, deliberately not a
trained model (docs/TRAINING.md #5). Slope failure typically follows
sustained saturation then an intensity spike; that is why the 15-day
term carries the most weight, not the 24-hour reading.

    trigger = 0.35*norm(rain_15d) + 0.30*norm(rain_3d)
            + 0.20*norm(rain_intensity_max) + 0.15*norm(soil_moisture)

Composite: risk = susceptibility * normalise(trigger). Both components
stay exposed separately through the API - a cell can be highly
susceptible and dry, and the officer must be able to see which.
"""

from __future__ import annotations

import numpy as np

_WEIGHTS = {"rain_15d": 0.35, "rain_3d": 0.30, "rain_intensity_max": 0.20, "soil_moisture": 0.15}


def _minmax_norm(values: np.ndarray, low_pct: float = 5.0, high_pct: float = 95.0) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    vmin, vmax = np.nanpercentile(values, low_pct), np.nanpercentile(values, high_pct)
    if vmax - vmin < 1e-12:
        return np.zeros_like(values)
    return np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)


def compute_trigger(
    rain_15d: np.ndarray,
    rain_3d: np.ndarray,
    rain_intensity_max: np.ndarray,
    soil_moisture: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    contributions = {
        "rain_15d": _WEIGHTS["rain_15d"] * _minmax_norm(rain_15d),
        "rain_3d": _WEIGHTS["rain_3d"] * _minmax_norm(rain_3d),
        "rain_intensity_max": _WEIGHTS["rain_intensity_max"] * _minmax_norm(rain_intensity_max),
        "soil_moisture": _WEIGHTS["soil_moisture"] * _minmax_norm(soil_moisture),
    }
    trigger_score = sum(contributions.values())
    return trigger_score, contributions


def composite_risk(susceptibility: np.ndarray, trigger_score: np.ndarray) -> np.ndarray:
    """risk = susceptibility * normalise(trigger). susceptibility is
    already 0..1 (M1's output); trigger_score is 0..1 by construction
    (each contribution is a weighted norm), so this stays in 0..1.
    """
    return np.clip(np.asarray(susceptibility, dtype=float) * np.asarray(trigger_score, dtype=float), 0.0, 1.0)
