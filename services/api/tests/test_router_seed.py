from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_seed_titli_creates_units_and_requests():
    response = client.post("/seed/titli")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "seeded"
    assert body["units_created"] >= 10
    assert body["requests_created"] >= 10

    units = client.get("/units").json()
    requests = client.get("/requests").json()
    assert len(units) == body["units_created"]
    assert len(requests) >= body["requests_created"]  # requests store may carry over from other tests


def test_seed_titli_is_repeatable():
    first = client.post("/seed/titli").json()
    second = client.post("/seed/titli").json()
    assert first["units_created"] == second["units_created"]
