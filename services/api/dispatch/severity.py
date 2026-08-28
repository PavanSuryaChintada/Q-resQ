"""Stage 04 triage: severity scoring. See BUILD_SPEC.md, docs/TRD.md #5.1.

Returns all four components, not just the total - the whole argument
for a formula over a black-box model is that the officer can see why
one request outranks another.

people and wait are normalised against the current queue's own max,
not a fixed constant, so severity is always relative to what's
actually happening right now.
"""

from __future__ import annotations

CATEGORY_WEIGHT = {"medical": 1.0, "stranded": 0.7, "evacuation": 0.5}


def compute_severity(
    people_count: int,
    category: str,
    area_risk: float,
    wait_minutes: float,
    max_people_in_queue: int,
    max_wait_minutes_in_queue: float,
) -> dict[str, float]:
    sev_people = 0.30 * (people_count / max_people_in_queue if max_people_in_queue > 0 else 0.0)
    sev_category = 0.30 * CATEGORY_WEIGHT.get(category, 0.5)
    sev_area_risk = 0.25 * max(0.0, min(area_risk, 1.0))
    sev_wait = 0.15 * (wait_minutes / max_wait_minutes_in_queue if max_wait_minutes_in_queue > 0 else 0.0)

    return {
        "severity": sev_people + sev_category + sev_area_risk + sev_wait,
        "sev_people": sev_people,
        "sev_category": sev_category,
        "sev_area_risk": sev_area_risk,
        "sev_wait": sev_wait,
    }
