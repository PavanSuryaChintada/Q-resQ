"""Solver protocol and the constraint gate. See BUILD_SPEC.md §4.

validate_constraints is the most important function in the package:
no solver's result may leave this module without passing it.
"""

from __future__ import annotations

from typing import Protocol

from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO


class Solver(Protocol):
    name: str

    def solve(self, qubo: QUBO, problem: DispatchProblem, timeout_s: float) -> DispatchResult: ...


def validate_constraints(assignments: list[tuple[str, str]]) -> bool:
    units = [u for u, _ in assignments]
    requests = [r for _, r in assignments]
    return len(units) == len(set(units)) and len(requests) == len(set(requests))
