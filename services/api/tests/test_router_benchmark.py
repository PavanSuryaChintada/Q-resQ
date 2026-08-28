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
