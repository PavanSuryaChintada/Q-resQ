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
    import routers.units as units_router
    for unit_id, unit in units_router._store.items():
        units_router._store[unit_id] = unit.model_copy(update={"status": "available"})


def test_run_returns_one_row_per_requested_backend_in_order():
    _free_all_units()
    _open_request()

    response = client.post("/benchmark/run", json={"backends": ["greedy", "ortools", "annealing"]})

    assert response.status_code == 200
    body = response.json()
    assert [row["backend"] for row in body["rows"]] == ["greedy", "ortools", "annealing"]
    for row in body["rows"]:
        assert row["constraints_valid"] is True


def test_run_with_no_open_requests_returns_422():
    import routers.requests as requests_router
    saved = dict(requests_router._store)
    requests_router._store.clear()
    try:
        response = client.post("/benchmark/run", json={"backends": ["greedy"]})
        assert response.status_code == 422
    finally:
        requests_router._store.update(saved)


def test_results_can_be_fetched_by_round_id():
    _free_all_units()
    _open_request()
    run = client.post("/benchmark/run", json={"backends": ["greedy"]}).json()

    response = client.get("/benchmark/results", params={"round_id": run["round_id"]})
    assert response.status_code == 200
    assert response.json() == run["rows"]


def test_results_404_for_unknown_round_id():
    response = client.get("/benchmark/results", params={"round_id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_run_caps_the_problem_so_qaoa_can_actually_run_on_it():
    # a queue with more than 5 open requests would build an
    # unpartitioned problem qaoa's 24-qubit guard always rejects -
    # /benchmark/run must cap to a subset qaoa can actually solve.
    # benchmark/run never mutates state (unlike dispatch/solve), so
    # these 8 requests would otherwise sit "open" for the rest of the
    # test session - save/restore the store like the 422 test does.
    import routers.requests as requests_router
    saved = dict(requests_router._store)
    _free_all_units()
    try:
        for _ in range(8):
            _open_request()

        response = client.post("/benchmark/run", json={"backends": ["qaoa"]})

        assert response.status_code == 200
        qaoa_row = response.json()["rows"][0]
        assert qaoa_row["backend"] == "qaoa"
        assert qaoa_row["constraints_valid"] is True
        assert qaoa_row["notes"] is None
    finally:
        requests_router._store.clear()
        requests_router._store.update(saved)
