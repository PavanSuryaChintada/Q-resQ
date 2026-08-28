"""qubo-dispatch: formulate emergency rescue dispatch as a QUBO."""

from qubo_dispatch.benchmark import benchmark
from qubo_dispatch.partition import partition, solve_partitioned
from qubo_dispatch.router import solve
from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO, Request, Unit

__all__ = [
    "DispatchProblem",
    "DispatchResult",
    "QUBO",
    "Request",
    "Unit",
    "benchmark",
    "partition",
    "solve",
    "solve_partitioned",
]
