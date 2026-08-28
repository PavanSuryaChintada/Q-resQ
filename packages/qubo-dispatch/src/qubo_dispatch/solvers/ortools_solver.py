"""OR-Tools CP-SAT baseline, constraints declared natively. See BUILD_SPEC.md §7.

The honest production baseline. Expect it to win.
"""

from __future__ import annotations

import time

from qubo_dispatch.formulation import evaluate
from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO


class OrtoolsSolver:
    name = "ortools"

    def solve(self, qubo: QUBO, problem: DispatchProblem, timeout_s: float) -> DispatchResult:
        from ortools.sat.python import cp_model

        start = time.monotonic()
        model = cp_model.CpModel()
        x = {k: model.NewBoolVar(f"x{k}") for k in range(qubo.n_vars)}

        for request in problem.requests:
            reachable = [x[qubo.index[(u.id, request.id)]] for u in problem.units
                         if (u.id, request.id) in qubo.index]
            if reachable:
                model.AddAtMostOne(reachable)

        for unit in problem.units:
            reachable = [x[qubo.index[(unit.id, r.id)]] for r in problem.requests
                         if (unit.id, r.id) in qubo.index]
            if reachable:
                model.AddAtMostOne(reachable)

        # each Q[(k,k)] is exactly -value_norm + alpha*travel_norm (no
        # penalty on the diagonal); maximise its negation
        model.Maximize(sum(-qubo.Q.get((k, k), 0.0) * x[k] for k in range(qubo.n_vars)))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_s
        status = solver.Solve(model)

        solution = {k: solver.Value(x[k]) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0
                    for k in range(qubo.n_vars)}
        assignments = [qubo.reverse[k] for k, v in solution.items() if v == 1]
        # report through the shared evaluator, not CP-SAT's internal
        # objective - the two use different sign conventions
        objective = evaluate(qubo, solution)
        solve_ms = int((time.monotonic() - start) * 1000)

        return DispatchResult(
            assignments=assignments,
            objective=objective,
            backend=self.name,
            fell_back=False,
            solve_ms=solve_ms,
            qubit_count=qubo.n_vars,
        )
