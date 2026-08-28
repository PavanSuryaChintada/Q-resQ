"""Auto-tune the constraint penalty from the objective bound. See BUILD_SPEC.md §3."""

from __future__ import annotations

from qubo_dispatch.types import DispatchProblem


def tune_penalty(problem: DispatchProblem, margin: float = 1.2) -> float:
    bound = 1.0 + problem.alpha * 1.0  # both terms normalised to 0..1
    # lambda must exceed the maximum objective gain from violating a
    # constraint, or the optimizer breaks it for points. But oversized
    # penalties flatten the energy landscape and stall COBYLA inside
    # QAOA — every feasible solution starts to look identical. 1.2x is
    # the smallest safe margin.
    return margin * bound
