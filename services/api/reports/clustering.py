"""Citizen report clustering.

Groups reports that are close in space and time to avoid duplicate
processing and identify hotspots.

Clustering criteria: within 100 m and within 60 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any




@dataclass
class ReportCluster:
    """A cluster of related citizen reports."""
    id: int
    centroid_lat: float
    centroid_lon: float
    report_count: int
    first_seen: datetime
    last_seen: datetime
    dominant_kind: str


@dataclass
class CitizenReport:
    """A citizen-submitted report."""
    id: str  # UUID
    location: tuple[float, float]  # (lat, lon)
    accuracy_m: float | None
    kind: str  # crack | slope_movement | road_blocked | water_seepage | other
    auto_class: str | None  # on-device ONNX output
    auto_conf: float | None  # confidence from auto-classification
    note: str | None
    media_url: str | None
    media_type: str | None  # image | video
    status: str  # pending | verified | dismissed | duplicate
    cluster_id: int | None
    reporter_hash: str  # hashed device id
    lang: str
    created_at: datetime
    synced_at: datetime
    reviewed_at: datetime | None


_CLUSTER_DISTANCE_M = 100.0
_CLUSTER_TIME_MINUTES = 60


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance between two points in meters."""
    from math import asin, cos, radians, sin, sqrt

    R = 6371000  # Earth radius in meters

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


def cluster_reports(reports: list[CitizenReport]) -> tuple[list[ReportCluster], list[CitizenReport]]:
    """Cluster reports by space and time.

    Groups reports that are within 100 m and 60 minutes of each other.

    Args:
        reports: List of citizen reports to cluster

    Returns:
        (clusters, updated_reports) where updated_reports have cluster_id assigned
    """
    if not reports:
        return [], []

    # Sort by time to process chronologically
    sorted_reports = sorted(reports, key=lambda r: r.created_at)

    clusters: list[ReportCluster] = []
    cluster_counter = 0

    # Assign cluster IDs
    for report in sorted_reports:
        assigned = False

        # Try to assign to existing cluster
        for cluster in clusters:
            # Check time window
            time_diff = abs((report.created_at - cluster.last_seen).total_seconds())
            if time_diff > _CLUSTER_TIME_MINUTES * 60:
                continue

            # Check distance
            dist = haversine_distance(
                report.location[0], report.location[1],
                cluster.centroid_lat, cluster.centroid_lon
            )
            if dist > _CLUSTER_DISTANCE_M:
                continue

            # Assign to this cluster
            report.cluster_id = cluster.id
            cluster.report_count += 1
            cluster.last_seen = max(cluster.last_seen, report.created_at)

            # Update centroid (simple average)
            cluster.centroid_lat = (
                cluster.centroid_lat * (cluster.report_count - 1) + report.location[0]
            ) / cluster.report_count
            cluster.centroid_lon = (
                cluster.centroid_lon * (cluster.report_count - 1) + report.location[1]
            ) / cluster.report_count

            assigned = True
            break

        # Create new cluster if not assigned
        if not assigned:
            cluster_counter += 1
            new_cluster = ReportCluster(
                id=cluster_counter,
                centroid_lat=report.location[0],
                centroid_lon=report.location[1],
                report_count=1,
                first_seen=report.created_at,
                last_seen=report.created_at,
                dominant_kind=report.kind,
            )
            clusters.append(new_cluster)
            report.cluster_id = cluster_counter

    # Update dominant kind for each cluster
    for cluster in clusters:
        cluster_reports = [r for r in sorted_reports if r.cluster_id == cluster.id]
        if cluster_reports:
            # Count kinds
            kind_counts = {}
            for r in cluster_reports:
                kind_counts[r.kind] = kind_counts.get(r.kind, 0) + 1
            # Get dominant kind
            cluster.dominant_kind = max(kind_counts, key=kind_counts.get)

    return clusters, sorted_reports


def get_hotspots(clusters: list[ReportCluster], min_reports: int = 3) -> list[ReportCluster]:
    """Get clusters that meet the hotspot threshold.

    Hotspots are clusters with at least min_reports reports.

    Args:
        clusters: List of report clusters
        min_reports: Minimum report count to be considered a hotspot

    Returns:
        List of hotspot clusters
    """
    return [c for c in clusters if c.report_count >= min_reports]


def deduplicate_reports(reports: list[CitizenReport]) -> list[CitizenReport]:
    """Mark duplicate reports.

    A report is considered a duplicate if it's in the same cluster as
    an earlier report with the same kind.

    Args:
        reports: List of citizen reports (should already be clustered)

    Returns:
        Updated reports with status="duplicate" for duplicates
    """
    # Group by cluster
    cluster_map: dict[int, list[CitizenReport]] = {}
    for report in reports:
        if report.cluster_id is not None:
            if report.cluster_id not in cluster_map:
                cluster_map[report.cluster_id] = []
            cluster_map[report.cluster_id].append(report)

    # Mark duplicates (keep first report of each kind per cluster)
    for cluster_id, cluster_reports in cluster_map.items():
        # Sort by time
        cluster_reports.sort(key=lambda r: r.created_at)

        # Track seen kinds
        seen_kinds = set()
        for report in cluster_reports:
            if report.kind in seen_kinds:
                report.status = "duplicate"
            else:
                seen_kinds.add(report.kind)

    return reports
