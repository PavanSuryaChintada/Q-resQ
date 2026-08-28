import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _payload(request_id=None):
    return {
        "id": str(request_id or uuid.uuid4()),
        "location": [18.30, 83.89],
        "people_count": 4,
        "category": "stranded",
        "note": "on the roof",
        "created_at": "2018-10-11T05:00:00Z",
    }


def test_create_returns_201_with_open_status():
    response = client.post("/requests", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["people_count"] == 4


def test_create_is_idempotent_on_client_generated_uuid():
    request_id = uuid.uuid4()
    first = client.post("/requests", json=_payload(request_id))
    second = client.post("/requests", json=_payload(request_id))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listing = client.get("/requests").json()
    matching = [r for r in listing if r["id"] == str(request_id)]
    assert len(matching) == 1  # replay did not create a duplicate


def test_patch_updates_status():
    request_id = uuid.uuid4()
    client.post("/requests", json=_payload(request_id))

    response = client.patch(f"/requests/{request_id}", json={"status": "assigned"})
    assert response.status_code == 200
    assert response.json()["status"] == "assigned"


def test_patch_404_for_unknown_id():
    response = client.patch(f"/requests/{uuid.uuid4()}", json={"status": "assigned"})
    assert response.status_code == 404


def test_sync_bulk_upserts_idempotently():
    request_id = uuid.uuid4()
    batch = [_payload(request_id)]

    first = client.post("/requests/sync", json=batch)
    second = client.post("/requests/sync", json=batch)  # replay the same batch

    assert first.status_code == 200
    assert second.status_code == 200
    listing = client.get("/requests").json()
    matching = [r for r in listing if r["id"] == str(request_id)]
    assert len(matching) == 1


def test_list_can_filter_by_status():
    request_id = uuid.uuid4()
    client.post("/requests", json=_payload(request_id))
    client.patch(f"/requests/{request_id}", json={"status": "resolved"})

    response = client.get("/requests", params={"status": "resolved"})
    assert response.status_code == 200
    assert any(r["id"] == str(request_id) for r in response.json())
    assert all(r["status"] == "resolved" for r in response.json())
