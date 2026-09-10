"""Stage 04 triage: severity scoring. See docs/TRD.md #5.1, docs/MIGRATION.md
sigma = 0.28*persons + 0.28*category + 0.22*area_risk + 0.12*wait + 0.10*isolation.

Returns all five components, not just the total - the whole argument
for a formula over a black-box model is that the officer can see why
one request outranks another.

isolation is the NER-specific term (docs/MIGRATION.md: "the single most
defensible addition to the triage model"): a settlement cut off by a
road blockage has no self-evacuation route, so its requests rank higher
independent of their own hazard exposure. Defaults to 0.0 (no isolation
signal / not near any settlement) rather than raising, since not every
caller has an isolation score to hand.

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
    isolation: float = 0.0,
) -> dict[str, float]:
    sev_people = 0.28 * (people_count / max_people_in_queue if max_people_in_queue > 0 else 0.0)
    sev_category = 0.28 * CATEGORY_WEIGHT.get(category, 0.5)
    sev_area_risk = 0.22 * max(0.0, min(area_risk, 1.0))
    sev_wait = 0.12 * (wait_minutes / max_wait_minutes_in_queue if max_wait_minutes_in_queue > 0 else 0.0)
    sev_isolation = 0.10 * max(0.0, min(isolation, 1.0))

    return {
        "severity": sev_people + sev_category + sev_area_risk + sev_wait + sev_isolation,
        "sev_people": sev_people,
        "sev_category": sev_category,
        "sev_area_risk": sev_area_risk,
        "sev_wait": sev_wait,
        "sev_isolation": sev_isolation,
    }
