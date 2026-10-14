from app.core.security import decrypt_api_key
from app.models.project import Project


def test_create_project(client, auth_headers_user1, user1):
    response = client.post(
        "/api/projects",
        headers=auth_headers_user1,
        json={
            "name": "Legal Summarizer",
            "description": "Contracts summarization prompt tests",
            "gemini_api_key": "AIzaSyD-sample-test-gemini-key-12345",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Legal Summarizer"
    assert data["has_api_key"] is True
    # Invariant 6: Plaintext API key must NEVER be exposed
    assert data["masked_api_key"] is not None
    assert "sample-test" not in data["masked_api_key"]
    assert data["masked_api_key"].startswith("AIzaSy")
    assert data["masked_api_key"].endswith("2345")


def test_list_and_get_project(client, auth_headers_user1, sample_project):
    response = client.get("/api/projects", headers=auth_headers_user1)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["id"] == sample_project.id for p in data)

    # Get single project
    res_single = client.get(f"/api/projects/{sample_project.id}", headers=auth_headers_user1)
    assert res_single.status_code == 200
    assert res_single.json()["name"] == sample_project.name


def test_update_project(client, auth_headers_user1, sample_project):
    response = client.put(
        f"/api/projects/{sample_project.id}",
        headers=auth_headers_user1,
        json={"name": "Updated Project Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Project Name"


def test_encrypted_gemini_api_key_at_rest(client, auth_headers_user1, sample_project, db_session):
    plain_key = "AIzaSySecretGeminiKey1234567890XYZ"
    res_set = client.post(
        f"/api/projects/{sample_project.id}/api-key",
        headers=auth_headers_user1,
        json={"api_key": plain_key},
    )
    assert res_set.status_code == 200
    assert res_set.json()["has_key"] is True
    assert res_set.json()["masked_key"].startswith("AIzaSy")
    assert "SecretGeminiKey" not in res_set.json()["masked_key"]

    # Invariant 5: Verify encrypted at rest in the database
    db_proj = db_session.query(Project).filter(Project.id == sample_project.id).first()
    assert db_proj.encrypted_gemini_api_key is not None
    assert db_proj.encrypted_gemini_api_key != plain_key
    assert "AIzaSySecretGeminiKey" not in db_proj.encrypted_gemini_api_key

    # Verify decryption works correctly internally
    decrypted = decrypt_api_key(db_proj.encrypted_gemini_api_key)
    assert decrypted == plain_key

    # Test delete api key
    res_del = client.delete(
        f"/api/projects/{sample_project.id}/api-key", headers=auth_headers_user1
    )
    assert res_del.status_code == 204

    res_status = client.get(
        f"/api/projects/{sample_project.id}/api-key", headers=auth_headers_user1
    )
    assert res_status.status_code == 200
    assert res_status.json()["has_key"] is False


def test_ownership_protection_on_projects(client, auth_headers_user2, sample_project):
    # Invariant 4: Every project route checks ownership (User 2 accessing User 1's project)
    res_get = client.get(f"/api/projects/{sample_project.id}", headers=auth_headers_user2)
    assert res_get.status_code == 403
    assert "do not own" in res_get.json()["detail"].lower()

    res_put = client.put(
        f"/api/projects/{sample_project.id}",
        headers=auth_headers_user2,
        json={"name": "Hacked Name"},
    )
    assert res_put.status_code == 403

    res_key = client.post(
        f"/api/projects/{sample_project.id}/api-key",
        headers=auth_headers_user2,
        json={"api_key": "hacker-key"},
    )
    assert res_key.status_code == 403

    res_del = client.delete(f"/api/projects/{sample_project.id}", headers=auth_headers_user2)
    assert res_del.status_code == 403
