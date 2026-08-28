import random

from qubo_dispatch.partition import partition, solve_partitioned
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _scattered_problem(n_units=15, n_requests=40, seed=0):
    rng = random.Random(seed)
    units = [Unit(id=f"u{i}", capacity=4, position=(rng.uniform(0, 10), rng.uniform(0, 10)))
             for i in range(n_units)]
    requests = [Request(id=f"r{j}", severity=rng.uniform(0, 1), people=rng.randint(1, 8),
                         position=(rng.uniform(0, 10), rng.uniform(0, 10)))
                for j in range(n_requests)]
    travel_time_s = {(u.id, r.id): rng.uniform(60, 3000) for u in units for r in requests}
    return DispatchProblem(units=units, requests=requests, travel_time_s=travel_time_s)


def test_every_request_lands_in_exactly_one_zone():
    problem = _scattered_problem()
    zones = partition(problem, max_requests_per_zone=5, max_units_per_zone=4)

    all_request_ids = [r.id for zone in zones for r in zone.requests]
    assert sorted(all_request_ids) == sorted(r.id for r in problem.requests)
    assert len(all_request_ids) == len(set(all_request_ids))  # no duplicates


def test_no_zone_exceeds_the_request_cap():
    problem = _scattered_problem()
    zones = partition(problem, max_requests_per_zone=5, max_units_per_zone=4)

    for zone in zones:
        assert len(zone.requests) <= 5


def test_no_zone_exceeds_the_unit_cap():
    problem = _scattered_problem()
    zones = partition(problem, max_requests_per_zone=5, max_units_per_zone=4)

    for zone in zones:
        assert len(zone.units) <= 4


def test_a_zone_only_keeps_travel_times_for_its_own_pairs():
    problem = _scattered_problem()
    zones = partition(problem, max_requests_per_zone=5, max_units_per_zone=4)

    for zone in zones:
        zone_unit_ids = {u.id for u in zone.units}
        zone_request_ids = {r.id for r in zone.requests}
        for (unit_id, request_id) in zone.travel_time_s:
            assert unit_id in zone_unit_ids
            assert request_id in zone_request_ids


def test_solve_partitioned_merges_zone_results_into_a_globally_valid_plan():
    problem = _scattered_problem(n_units=15, n_requests=40)

    result = solve_partitioned(problem, backend="greedy", max_requests_per_zone=5, max_units_per_zone=4)

    assert validate_constraints(result.assignments) is True
    assert len(result.assignments) > 0


def test_solve_partitioned_handles_more_zones_than_units_gracefully():
    # far more request-zones than units - some zones get zero units and
    # must be skipped, not solved
    problem = _scattered_problem(n_units=3, n_requests=40)

    result = solve_partitioned(problem, backend="greedy", max_requests_per_zone=5, max_units_per_zone=4)

    assert validate_constraints(result.assignments) is True
    assert len(result.assignments) <= 3
