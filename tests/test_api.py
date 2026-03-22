import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.store import store
import time

client = TestClient(app)


# reset store state before each test
@pytest.fixture(autouse=True)
def reset_store():
    store._users.clear()
    store._next_id = 1


# user endpoint tests
def test_create_user():
    response = client.post("/users")
    data = response.json()
    assert response.status_code == 201
    assert data["id"] == 1


def test_create_user_auto_increments_id():
    response1 = client.post("/users")
    response2 = client.post("/users")

    data1 = response1.json()
    assert response1.status_code == 201
    assert data1["id"] == 1

    data2 = response2.json()
    assert response2.status_code == 201
    assert data2["id"] == 2


# requests endpoint tests
def test_record_request_success():
    user_data = client.post("/users").json()
    request_response = client.post("/requests", json={"user_id": user_data["id"]})
    request_data = request_response.json()

    assert request_response.status_code == 201
    assert request_data["user_id"] == user_data["id"]
    assert request_data["remaining"] == 9
    assert request_data["resets_in_seconds"] > 0


def test_record_request_decrements_remaining():
    user_data = client.post("/users").json()
    client.post("/requests", json={"user_id": user_data["id"]})
    client.post("/requests", json={"user_id": user_data["id"]})
    request_response = client.post("/requests", json={"user_id": user_data["id"]})
    request_data = request_response.json()

    assert request_response.status_code == 201
    assert request_data["user_id"] == user_data["id"]
    assert request_data["remaining"] == 7
    assert request_data["resets_in_seconds"] > 0


def test_record_request_rate_limits_at_max():
    user_data = client.post("/users").json()
    for _ in range(10):
        client.post("/requests", json={"user_id": user_data["id"]})

    request_response = client.post("/requests", json={"user_id": user_data["id"]})
    assert request_response.status_code == 429
    assert "Retry-After" in request_response.headers
    assert int(request_response.headers.get("Retry-After")) > 0


def test_record_request_user_not_found():
    response = client.post("/requests", json={"user_id": 1})
    assert response.status_code == 404


def test_record_request_missing_user_id():
    response = client.post("/requests")
    assert response.status_code == 422


def test_record_request_invalid_user_id():
    response = client.post("/requests", json={"user_id": "string"})
    assert response.status_code == 422


def test_record_request_independent_user_quotas():
    user_data_1 = client.post("/users").json()
    user_data_2 = client.post("/users").json()

    request_response_1 = client.post("/requests", json={"user_id": user_data_1["id"]})
    request_response_2 = client.post("/requests", json={"user_id": user_data_2["id"]})
    request_data_1 = request_response_1.json()
    request_data_2 = request_response_2.json()

    assert request_data_1["user_id"] == user_data_1["id"]
    assert request_data_1["remaining"] == 9
    assert request_data_1["resets_in_seconds"] > 0

    assert request_data_2["user_id"] == user_data_2["id"]
    assert request_data_2["remaining"] == 9
    assert request_data_2["resets_in_seconds"] > 0


def test_record_request_resets_after_window():
    user_data = client.post("/users").json()
    for _ in range(10):
        client.post("/requests", json={"user_id": user_data["id"]})

    # Verify we're rate limited
    response = client.post("/requests", json={"user_id": user_data["id"]})
    assert response.status_code == 429

    # Jump forward 61 seconds
    future = time.time() + 61
    # this could be done with ptyest monkeypatch also
    with (
        patch("app.store.time") as mock_time
    ):  # temporaly swap time module that exists inside app/store.py with fake object
        mock_time.time.return_value = (
            future  # configure fake modules .time() method to return future
        )
        response = client.post("/requests", json={"user_id": user_data["id"]})
        assert response.status_code == 201
        assert response.json()["remaining"] == 9


# quota endpoints tests
def test_get_quota_fresh_user():
    user_data = client.post("/users").json()
    user_quota = client.get(f"/users/{user_data['id']}/quota").json()
    assert user_quota["used"] == 0
    assert user_quota["remaining"] == 10
    assert user_quota["resets_in_seconds"] == 0


def test_get_quota_reflects_used_requests():

    user_data = client.post("/users").json()

    # make 5 request
    for _ in range(5):
        client.post("/requests", json={"user_id": user_data["id"]})

    user_quota = client.get(f"/users/{user_data['id']}/quota").json()

    assert user_quota["used"] == 5
    assert user_quota["remaining"] == 5
    assert user_quota["resets_in_seconds"] > 0


def test_get_quota_after_rate_limit():

    user_data = client.post("/users").json()

    # make 10 request
    for _ in range(10):
        client.post("/requests", json={"user_id": user_data["id"]})

    user_quota = client.get(f"/users/{user_data['id']}/quota").json()

    assert user_quota["used"] == 10
    assert user_quota["remaining"] == 0
    assert user_quota["resets_in_seconds"] > 0


def test_quota_user_not_found():
    user_quota_response = client.get("/users/1/quota")
    assert user_quota_response.status_code == 404


def test_quota_invalid_id():
    user_quota_response = client.get("/users/abc/quota")
    assert user_quota_response.status_code == 422


def test_quota_resets_after_time_window():

    user_data = client.post("/users").json()
    for _ in range(10):
        client.post("/requests", json={"user_id": user_data["id"]})

    # Verify we're rate limited
    response = client.post("/requests", json={"user_id": user_data["id"]})
    assert response.status_code == 429

    # Jump forward 61 seconds
    future = time.time() + 61
    # this could be done with ptyest monkeypatch also
    with (
        patch("app.store.time") as mock_time
    ):  # temporaly swap time module that exists inside app/store.py with fake object
        mock_time.time.return_value = (
            future  # configure fake modules .time() method to return future
        )
        user_quota = client.get(f"/users/{user_data['id']}/quota").json()
        assert user_quota["remaining"] == 10
        assert user_quota["used"] == 0
