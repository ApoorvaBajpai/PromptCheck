from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "version" in data


def test_healthz_healthy():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert "timestamp" in data


def test_healthz_unhealthy_db():
    class BrokenDB:
        def execute(self, statement):
            raise OperationalError("connection failure", params=None, orig=Exception("DB down"))

    def override_get_db():
        yield BrokenDB()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/healthz")
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["status"] == "unhealthy"
        assert "error" in data["detail"]["database"]
    finally:
        app.dependency_overrides.clear()
