import pytest
from fastapi.testclient import TestClient

import login_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(login_app, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(login_app.app) as test_client:
        yield test_client


def register(client, username="anna", password="parole123", confirm=None):
    return client.post(
        "/register",
        data={"username": username, "password": password, "password_confirm": confirm or password},
    )


def test_anonymous_user_is_redirected_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_register_logs_in_and_entries_are_saved(client):
    assert register(client).status_code == 200

    response = client.post("/entries", data={"title": "Pirmais", "body": "Sveika, <pasaule>"})
    assert response.status_code == 200
    assert "Pirmais" in response.text
    assert "&lt;pasaule&gt;" in response.text


def test_login_with_existing_user(client):
    register(client)
    client.post("/logout")
    client.cookies.clear()

    assert client.post("/login", data={"username": "anna", "password": "nepareiza"}).status_code == 401
    response = client.post("/login", data={"username": "anna", "password": "parole123"})
    assert response.status_code == 200
    assert "Mani ieraksti" in response.text


def test_password_is_not_stored_in_plain_text(client):
    register(client)
    with login_app.connect() as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()["password_hash"]
    assert "parole123" not in stored
    assert login_app.verify_password("parole123", stored)


def test_register_validation(client):
    assert register(client, password="īsa").status_code == 400
    assert register(client, confirm="cita-parole").status_code == 400
    register(client)
    client.cookies.clear()
    assert register(client).status_code == 409


def test_users_see_only_their_own_entries(client):
    register(client, username="anna")
    client.post("/entries", data={"title": "Annas ieraksts", "body": "x"})
    client.cookies.clear()

    register(client, username="janis")
    assert "Annas ieraksts" not in client.get("/").text
