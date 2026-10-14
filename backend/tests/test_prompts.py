import hashlib


def test_create_prompt_with_initial_version(client, auth_headers_user1, sample_project):
    content = "You are a friendly customer assistant.\nAnswer queries accurately."
    response = client.post(
        f"/api/projects/{sample_project.id}/prompts",
        headers=auth_headers_user1,
        json={
            "name": "Customer Support System Prompt",
            "description": "Base instruction set",
            "initial_content": content,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Customer Support System Prompt"
    assert data["versions_count"] == 1
    assert data["latest_version"]["version_number"] == 1
    assert data["latest_version"]["content"] == content
    expected_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
    assert data["latest_version"]["content_hash"] == expected_hash


def test_prompt_version_deduplication_via_sha256(client, auth_headers_user1, sample_project):
    # Invariant 2: Identical prompt content must be deduplicated using SHA-256
    res_prompt = client.post(
        f"/api/projects/{sample_project.id}/prompts",
        headers=auth_headers_user1,
        json={"name": "Deduplication Prompt"},
    )
    prompt_id = res_prompt.json()["id"]

    prompt_text = "Summarize the customer request in 3 bullet points."

    # First creation -> version 1
    res_v1 = client.post(
        f"/api/projects/{sample_project.id}/prompts/{prompt_id}/versions",
        headers=auth_headers_user1,
        json={"content": prompt_text, "commit_message": "Version 1 draft"},
    )
    assert res_v1.status_code == 201
    v1_data = res_v1.json()
    assert v1_data["version_number"] == 1

    # Second creation with identical content -> Must deduplicate and return existing version 1!
    res_v2 = client.post(
        f"/api/projects/{sample_project.id}/prompts/{prompt_id}/versions",
        headers=auth_headers_user1,
        json={"content": f"  {prompt_text}  ", "commit_message": "Duplicate submission"},
    )
    assert res_v2.status_code == 201
    v2_data = res_v2.json()
    # Deduplication verified: Returned same version ID, version number 1, no duplicate row
    assert v2_data["id"] == v1_data["id"]
    assert v2_data["version_number"] == 1
    assert v2_data["content_hash"] == v1_data["content_hash"]

    # Verify listing versions still only contains 1 version
    res_list = client.get(
        f"/api/projects/{sample_project.id}/prompts/{prompt_id}/versions",
        headers=auth_headers_user1,
    )
    assert len(res_list.json()) == 1

    # Now create modified content -> Should increment to version 2
    modified_text = "Summarize the customer request in 5 bullet points with citations."
    res_v3 = client.post(
        f"/api/projects/{sample_project.id}/prompts/{prompt_id}/versions",
        headers=auth_headers_user1,
        json={"content": modified_text, "commit_message": "Version 2 modified"},
    )
    assert res_v3.status_code == 201
    v3_data = res_v3.json()
    assert v3_data["version_number"] == 2
    assert v3_data["id"] != v1_data["id"]


def test_prompt_ownership_protection(
    client, auth_headers_user1, auth_headers_user2, sample_project
):
    # User 1 creates prompt
    res = client.post(
        f"/api/projects/{sample_project.id}/prompts",
        headers=auth_headers_user1,
        json={"name": "Confidential Prompt", "initial_content": "Secret content"},
    )
    prompt_id = res.json()["id"]

    # User 2 attempts to view prompts (Invariant 4)
    res_user2 = client.get(
        f"/api/projects/{sample_project.id}/prompts",
        headers=auth_headers_user2,
    )
    assert res_user2.status_code == 403

    # User 2 attempts to create version on User 1's prompt
    res_create_v = client.post(
        f"/api/projects/{sample_project.id}/prompts/{prompt_id}/versions",
        headers=auth_headers_user2,
        json={"content": "Malicious payload"},
    )
    assert res_create_v.status_code == 403
