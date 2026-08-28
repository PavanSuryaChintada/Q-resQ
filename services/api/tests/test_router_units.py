from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_units_returns_fixture_units():
    response = client.get("/units")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    for unit in body:
        assert unit["status"] in ("available", "assigned", "en_route", "returning", "offline")
        assert unit["kind"] in ("boat", "ambulance", "truck", "team")


def test_patch_changes_unit_status():
    unit_id = client.get("/units").json()[0]["id"]

    response = client.patch(f"/units/{unit_id}", json={"status": "offline"})
    assert response.status_code == 200
    assert response.json()["status"] == "offline"

    listing = client.get("/units").json()
    matching = next(u for u in listing if u["id"] == unit_id)
    assert matching["status"] == "offline"


def test_patch_404_for_unknown_id():
    import uuid
    response = client.patch(f"/units/{uuid.uuid4()}", json={"status": "offline"})
    assert response.status_code == 404
