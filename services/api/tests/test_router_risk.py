from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_risk_cells_returns_a_geojson_feature_collection():
    response = client.get("/risk/cells")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 1
    feature = body["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] in ("Point", "Polygon")
    assert "risk_score" in feature["properties"]
    assert "risk_band" in feature["properties"]


def test_risk_cell_detail_includes_top_three_feature_contributions():
    response = client.get("/risk/cell/1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert 0 <= body["risk_score"] <= 1
    assert 0 <= body["risk_band"] <= 4
    assert len(body["top_features"]) == 3
    for feature in body["top_features"]:
        assert set(feature.keys()) == {"name", "value", "contribution"}


def test_risk_cell_detail_404_for_unknown_id():
    response = client.get("/risk/cell/999999")
    assert response.status_code == 404
