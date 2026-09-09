"""InSAR deformation data loading and classification.

This module loads pre-computed deformation time series from Sentinel-1
SBAS interferometry and classifies points by alert state.

Deformation is pre-computed offline and served as static data. Live
processing is a compute-scheduling problem, not an algorithmic one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_API_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = _API_DIR / "data" / "raw"

# Alert state thresholds (mm/yr)
_STABLE_THRESHOLD = 5.0  # below this = stable
_CREEPING_THRESHOLD = 20.0  # between stable and creeping = creeping


@dataclass
class DeformationPoint:
    """A single InSAR deformation point."""
    id: int
    lon: float
    lat: float
    corridor_id: str
    velocity_mm_yr: float
    coherence: float
    acceleration: float
    alert_state: str  # stable | creeping | accelerating
    n_acquisitions: int
    first_date: str
    last_date: str
    synthetic: bool  # TRUE if this is synthetic demo data, not measured


@dataclass
class DeformationSeries:
    """Time series for a single deformation point."""
    point_id: int
    acq_date: str
    displacement_mm: float


@dataclass
class InsarCorridor:
    """A processed InSAR corridor boundary."""
    id: str
    description: str
    track: int
    orbit_dir: str
    n_scenes: int
    # GeoJSON polygon geometry would be here in production


def classify_alert_state(velocity_mm_yr: float, acceleration: float) -> str:
    """Classify a point's alert state based on velocity and acceleration.

    Stable: velocity < 5 mm/yr
    Creeping: velocity >= 5 mm/yr, acceleration not significant
    Accelerating: acceleration > threshold (this is the warning signal)
    """
    if abs(velocity_mm_yr) < _STABLE_THRESHOLD:
        return "stable"
    elif acceleration > 1.0:  # mm/yr^2 threshold for acceleration
        return "accelerating"
    else:
        return "creeping"


def load_demo_corridor_data() -> tuple[list[DeformationPoint], list[DeformationSeries], InsarCorridor]:
    """Load demo corridor deformation data from CSV.

    This loads pre-computed deformation data for the NH6 corridor in Aizawl.
    The data is sourced from the demo CSV file which represents synthetic
    but realistic deformation patterns.

    Returns:
        (deformation_points, time_series, corridor_info)
    """
    # Load deformation points from CSV
    csv_path = DATA_DIR / "insar_demo_corridor.csv"
    if not csv_path.exists():
        print("[insar] Demo CSV not found, using synthetic data")
        return _generate_synthetic_data()

    df = pd.read_csv(csv_path)

    points = []
    for _, row in df.iterrows():
        points.append(DeformationPoint(
            id=int(row["id"]),
            lon=float(row["lon"]),
            lat=float(row["lat"]),
            corridor_id=str(row["corridor_id"]),
            velocity_mm_yr=float(row["velocity_mm_yr"]),
            coherence=float(row["coherence"]),
            acceleration=float(row["acceleration"]),
            alert_state=str(row["alert_state"]),
            n_acquisitions=int(row["n_acquisitions"]),
            first_date=str(row["first_date"]),
            last_date=str(row["last_date"]),
        ))

    # Generate synthetic time series for each point
    series = []
    for point in points:
        rng = np.random.RandomState(point.id)
        # Generate ~12-day Sentinel-1 revisit dates
        from datetime import datetime, timedelta
        start_date = datetime(2023, 1, 15)
        end_date = datetime(2024, 6, 30)
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=12)

        # Base displacement on velocity
        base_displacement = rng.normal(point.velocity_mm_yr / 12, 2, len(dates))  # monthly displacement
        cumulative = np.cumsum(base_displacement)

        for j, date in enumerate(dates):
            series.append(DeformationSeries(
                point_id=point.id,
                acq_date=date.strftime("%Y-%m-%d"),
                displacement_mm=float(cumulative[j]),
            ))

    corridor = InsarCorridor(
        id="demo_nh6",
        description="NH6 corridor, Aizawl district (demo data from CSV)",
        track=143,
        orbit_dir="descending",
        n_scenes=45,
    )

    return points, series, corridor


def _generate_synthetic_data() -> tuple[list[DeformationPoint], list[DeformationSeries], InsarCorridor]:
    """Fallback: generate synthetic data if CSV not available.

    IMPORTANT: This returns synthetic demonstration data, NOT measured deformation.
    All points are marked with synthetic=True and the corridor is labeled
    as illustrative only. This is for demo purposes pending real SLC acquisition.
    """
    corridor = InsarCorridor(
        id="demo_nh6_synthetic",
        description="NH6 corridor, Aizawl district (SYNTHETIC - ILLUSTRATIVE ONLY - NOT MEASURED)",
        track=143,
        orbit_dir="descending",
        n_scenes=45,
    )

    points = []
    for i in range(20):
        lon = 92.5 + i * 0.01
        lat = 23.7 + (i % 5) * 0.005
        rng = np.random.RandomState(i)
        velocity = rng.normal(0, 10)
        coherence = rng.uniform(0.3, 0.9)
        acceleration = rng.normal(0, 2)
        coherence = max(coherence, 0.3)
        alert_state = classify_alert_state(velocity, acceleration)

        points.append(DeformationPoint(
            id=i,
            lon=lon,
            lat=lat,
            corridor_id=corridor.id,
            velocity_mm_yr=float(velocity),
            coherence=float(coherence),
            acceleration=float(acceleration),
            alert_state=alert_state,
            n_acquisitions=45,
            first_date="2023-01-15",
            last_date="2024-06-30",
            synthetic=True,  # MARK AS SYNTHETIC
        ))

    series = []
    for point in points:
        rng = np.random.RandomState(point.id)
        from datetime import datetime, timedelta
        start_date = datetime(2023, 1, 15)
        end_date = datetime(2024, 6, 30)
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=12)

        base_displacement = rng.normal(0, 5, len(dates))
        cumulative = np.cumsum(base_displacement)

        for j, date in enumerate(dates):
            series.append(DeformationSeries(
                point_id=point.id,
                acq_date=date.strftime("%Y-%m-%d"),
                displacement_mm=float(cumulative[j]),
            ))

    return points, series, corridor


def get_deformation_points(corridor_id: str | None = None) -> list[DeformationPoint]:
    """Get deformation points, optionally filtered by corridor.

    Args:
        corridor_id: If provided, only return points from this corridor

    Returns:
        List of deformation points
    """
    points, _, _ = load_demo_corridor_data()

    if corridor_id is not None:
        points = [p for p in points if p.corridor_id == corridor_id]

    # Filter out low coherence points (< 0.3)
    points = [p for p in points if p.coherence >= 0.3]

    return points


def get_deformation_series(point_id: int) -> list[DeformationSeries]:
    """Get time series for a specific deformation point.

    Args:
        point_id: ID of the point

    Returns:
        List of time series entries
    """
    _, series, _ = load_demo_corridor_data()
    return [s for s in series if s.point_id == point_id]


def get_corridors() -> list[InsarCorridor]:
    """Get all processed InSAR corridors.

    Returns:
        List of corridor metadata
    """
    _, _, corridor = load_demo_corridor_data()
    return [corridor]


def get_accelerating_points(corridor_id: str | None = None) -> list[DeformationPoint]:
    """Get points with accelerating deformation (alert state).

    These are the points that should trigger alerts.

    Args:
        corridor_id: If provided, only return points from this corridor

    Returns:
        List of accelerating points
    """
    points = get_deformation_points(corridor_id)
    return [p for p in points if p.alert_state == "accelerating"]
