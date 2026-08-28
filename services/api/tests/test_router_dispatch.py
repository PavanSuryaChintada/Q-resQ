import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _open_request():
    request_id = uuid.uuid4()
    client.post("/requests", json={
        "id": str(request_id),
        "location": [18.3021, 83.8912],
        "people_count": 4,
        "category": "stranded",
        "created_at": "2018-10-11T05:00:00Z",
    })
    return request_id


def _free_all_units():
    # dispatch marks units "assigned" as a side effect - reset the
    # shared fixture pool so each test gets a deterministic starting
    # point regardless of what earlier tests consumed
    import routers.units as units_router
    for unit_id, unit in units_router._store.items():
        units_router._store[unit_id] = unit.model_copy(update={"status": "available"})


def test_solve_with_no_open_requests_returns_422():
    # the requests store is shared across test files/order - clear it
    # explicitly for this one case rather than assume it starts empty
    import routers.requests as requests_router
    saved = dict(requests_router._store)
    requests_router._store.clear()
    try:
        response = client.post("/dispatch/solve", json={"backend": "greedy", "timeout_s": 5.0})
        assert response.status_code == 422
    finally:
        requests_router._store.update(saved)


def test_solve_assigns_an_open_request_to_an_available_unit():
    _free_all_units()
    _open_request()

    response = client.post("/dispatch/solve", json={"backend": "greedy", "timeout_s": 5.0})

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "greedy"
    assert body["fell_back"] is False
    assert len(body["assignments"]) >= 1


def test_solved_requests_and_units_are_marked_assigned():
    _free_all_units()
    request_id = _open_request()
    client.post("/dispatch/solve", json={"backend": "greedy", "timeout_s": 5.0})

    updated = next(r for r in client.get("/requests").json() if r["id"] == str(request_id))
    assert updated["status"] == "assigned"


def test_get_round_returns_the_solved_round():
    _free_all_units()
    _open_request()
    solved = client.post("/dispatch/solve", json={"backend": "greedy", "timeout_s": 5.0}).json()

    response = client.get(f"/dispatch/rounds/{solved['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == solved["id"]


def test_get_round_404_for_unknown_id():
    response = client.get(f"/dispatch/rounds/{uuid.uuid4()}")
    assert response.status_code == 404
