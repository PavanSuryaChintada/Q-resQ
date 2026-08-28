from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_log_starts_empty_or_accumulates_in_order():
    import routers.log as log_router
    log_router._log.clear()
    log_router._next_id = 1

    log_router.append("system", "line one", severity=0)
    log_router.append("dispatch", "line two", severity=1)

    response = client.get("/log")
    assert response.status_code == 200
    body = response.json()
    assert [line["message"] for line in body] == ["line one", "line two"]
    assert body[0]["channel"] == "system"
    assert body[1]["severity"] == 1


def test_since_filters_to_lines_after_a_given_id():
    import routers.log as log_router
    log_router._log.clear()
    log_router._next_id = 1

    log_router.append("system", "first")
    log_router.append("system", "second")
    log_router.append("system", "third")

    response = client.get("/log", params={"since": 1})
    messages = [line["message"] for line in response.json()]
    assert messages == ["second", "third"]


def test_dispatch_solve_writes_a_ledger_line():
    import uuid

    import routers.log as log_router
    import routers.units as units_router
    log_router._log.clear()
    log_router._next_id = 1
    for unit_id, unit in units_router._store.items():
        units_router._store[unit_id] = unit.model_copy(update={"status": "available"})

    request_id = uuid.uuid4()
    client.post("/requests", json={
        "id": str(request_id),
        "location": [18.3021, 83.8912],
        "people_count": 4,
        "category": "stranded",
        "created_at": "2018-10-11T05:00:00Z",
    })
    client.post("/dispatch/solve", json={"backend": "greedy", "timeout_s": 5.0})

    response = client.get("/log")
    lines = response.json()
    assert any(line["channel"] == "dispatch" and "greedy" in line["message"] for line in lines)


def test_request_intake_writes_a_ledger_line():
    import uuid

    import routers.log as log_router
    log_router._log.clear()
    log_router._next_id = 1

    request_id = uuid.uuid4()
    client.post("/requests", json={
        "id": str(request_id),
        "location": [18.30, 83.89],
        "people_count": 2,
        "category": "medical",
        "created_at": "2018-10-11T05:00:00Z",
    })

    lines = client.get("/log").json()
    assert any(line["channel"] == "intake" and str(request_id) in line["message"] for line in lines)
