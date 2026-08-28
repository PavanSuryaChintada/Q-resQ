from qubo_dispatch.solvers.base import validate_constraints


def test_valid_when_every_unit_and_request_appears_at_most_once():
    assert validate_constraints([("u1", "r1"), ("u2", "r2")]) is True


def test_invalid_when_a_unit_is_double_booked():
    assert validate_constraints([("u1", "r1"), ("u1", "r2")]) is False


def test_invalid_when_a_request_is_double_booked():
    assert validate_constraints([("u1", "r1"), ("u2", "r1")]) is False


def test_empty_assignment_list_is_valid():
    assert validate_constraints([]) is True
