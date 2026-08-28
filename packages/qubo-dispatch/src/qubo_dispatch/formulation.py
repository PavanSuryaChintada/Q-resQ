"""Build a QUBO from a DispatchProblem. See BUILD_SPEC.md §2."""

from __future__ import annotations

from qubo_dispatch.types import DispatchProblem, QUBO


def build_qubo(problem: DispatchProblem, lam: float) -> QUBO:
    index: dict[tuple[str, str], int] = {}
    reverse: dict[int, tuple[str, str]] = {}
    k = 0
    for unit in problem.units:
        for request in problem.requests:
            pair = (unit.id, request.id)
            if pair not in problem.travel_time_s:
                continue  # unreachable: no variable, shrinks the QUBO for free
            index[pair] = k
            reverse[k] = pair
            k += 1

    max_value = max((r.severity * r.people for r in problem.requests), default=0.0)
    max_travel = max(problem.travel_time_s.values(), default=0.0)

    requests_by_id = {r.id: r for r in problem.requests}
    Q: dict[tuple[int, int], float] = {}
    for (unit_id, request_id), k_idx in index.items():
        request = requests_by_id[request_id]
        value_norm = (request.severity * request.people) / max_value if max_value else 0.0
        travel_norm = problem.travel_time_s[(unit_id, request_id)] / max_travel if max_travel else 0.0
        Q[(k_idx, k_idx)] = -value_norm + problem.alpha * travel_norm

    def add_penalty(k1: int, k2: int) -> None:
        key = (k1, k2) if k1 < k2 else (k2, k1)
        Q[key] = Q.get(key, 0.0) + 2.0 * lam

    # constraint 1: at most one unit per request
    for request in problem.requests:
        reachable = [index[(u.id, request.id)] for u in problem.units
                     if (u.id, request.id) in index]
        for i in range(len(reachable)):
            for j in range(i + 1, len(reachable)):
                add_penalty(reachable[i], reachable[j])

    # constraint 2: at most one request per unit
    for unit in problem.units:
        reachable = [index[(unit.id, r.id)] for r in problem.requests
                     if (unit.id, r.id) in index]
        for i in range(len(reachable)):
            for j in range(i + 1, len(reachable)):
                add_penalty(reachable[i], reachable[j])

    return QUBO(Q=Q, n_vars=k, index=index, reverse=reverse, lam=lam)


def evaluate(qubo: QUBO, x: dict[int, int]) -> float:
    total = qubo.offset
    for (i, j), coeff in qubo.Q.items():
        total += coeff * x.get(i, 0) * x.get(j, 0)
    return total
