from fastapi.testclient import TestClient


def test_health_returns_envelope_shape(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body == {
        "status": "success",
        "data": {"service": "ok"},
        "metadata": {
            "state": "fresh",
            "warnings": [],
        },
        "error": None,
    }


def test_health_envelope_top_level_keys(client: TestClient) -> None:
    body = client.get("/health").json()

    assert set(body.keys()) == {"status", "data", "metadata", "error"}
    assert body["status"] == "success"
    assert body["error"] is None
    assert body["metadata"]["state"] == "fresh"
    assert body["metadata"]["warnings"] == []
