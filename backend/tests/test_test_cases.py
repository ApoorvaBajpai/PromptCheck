def test_create_and_get_test_case(client, auth_headers_user1, sample_project):
    payload = {
        "name": "Refund Policy Query",
        "inputs": {"user_query": "How do I request a refund?"},
        "expected_output": "Refunds are processed within 5-7 business days.",
        "assertions": [
            {"type": "contains", "value": "5-7 business days"},
            {"type": "max_length", "value": 300},
        ],
    }
    response = client.post(
        f"/api/projects/{sample_project.id}/tests",
        headers=auth_headers_user1,
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Refund Policy Query"
    assert data["is_active"] is True
    assert data["inputs"]["user_query"] == "How do I request a refund?"
    test_id = data["id"]

    # Get single test
    res_get = client.get(
        f"/api/projects/{sample_project.id}/tests/{test_id}",
        headers=auth_headers_user1,
    )
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Refund Policy Query"


def test_soft_deletion_and_reactivation(client, auth_headers_user1, sample_project):
    # Invariant 3: Test deletion is soft deletion
    res_create = client.post(
        f"/api/projects/{sample_project.id}/tests",
        headers=auth_headers_user1,
        json={"name": "Temporary Test", "inputs": {"q": "temp"}},
    )
    test_id = res_create.json()["id"]

    # Delete test case
    res_delete = client.delete(
        f"/api/projects/{sample_project.id}/tests/{test_id}",
        headers=auth_headers_user1,
    )
    assert res_delete.status_code == 204

    # Default list must exclude deactivated / soft-deleted test
    res_list = client.get(
        f"/api/projects/{sample_project.id}/tests",
        headers=auth_headers_user1,
    )
    assert not any(t["id"] == test_id for t in res_list.json())

    # Query with include_inactive=true should still find it (record preserved)
    res_all = client.get(
        f"/api/projects/{sample_project.id}/tests?include_inactive=true",
        headers=auth_headers_user1,
    )
    soft_deleted = next((t for t in res_all.json() if t["id"] == test_id), None)
    assert soft_deleted is not None
    assert soft_deleted["is_active"] is False
    assert soft_deleted["deleted_at"] is not None

    # Test reactivation via PUT
    res_reactivate = client.put(
        f"/api/projects/{sample_project.id}/tests/{test_id}",
        headers=auth_headers_user1,
        json={"is_active": True},
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["is_active"] is True
    assert res_reactivate.json()["deleted_at"] is None


def test_json_batch_import(client, auth_headers_user1, sample_project):
    batch_payload = {
        "tests": [
            {
                "name": "Batch Test 1",
                "inputs": {"prompt_var": "val1"},
                "assertions": [{"type": "contains", "value": "val1"}],
            },
            {
                "name": "Batch Test 2",
                "inputs": {"prompt_var": "val2"},
                "assertions": [{"type": "not_contains", "value": "forbidden"}],
            },
        ]
    }
    response = client.post(
        f"/api/projects/{sample_project.id}/tests/import",
        headers=auth_headers_user1,
        json=batch_payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported_count"] == 2
    assert len(data["test_cases"]) == 2
    assert data["test_cases"][0]["name"] == "Batch Test 1"


def test_csv_file_import(client, auth_headers_user1, sample_project):
    csv_content = """name,input,expected_output,assertions
CSV Greeting,Hello World,Hi there,"[{""type"": ""contains"", ""value"": ""Hi""}]"
CSV Farewells,Goodbye,See you,"[{""type"": ""contains"", ""value"": ""See you""}]"
"""
    files = {"file": ("tests.csv", csv_content.encode("utf-8"), "text/csv")}
    response = client.post(
        f"/api/projects/{sample_project.id}/tests/import-file",
        headers=auth_headers_user1,
        files=files,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported_count"] == 2
    assert data["test_cases"][0]["name"] == "CSV Greeting"
    assert data["test_cases"][0]["inputs"] == {"input": "Hello World"}
    assert data["test_cases"][1]["name"] == "CSV Farewells"


def test_test_case_ownership_protection(
    client, auth_headers_user1, auth_headers_user2, sample_project
):
    # Invariant 4: Ownership protection on test cases
    res_create = client.post(
        f"/api/projects/{sample_project.id}/tests",
        headers=auth_headers_user1,
        json={"name": "Owner Only Test", "inputs": {}},
    )
    test_id = res_create.json()["id"]

    # User 2 attempts to view tests
    res_list = client.get(
        f"/api/projects/{sample_project.id}/tests",
        headers=auth_headers_user2,
    )
    assert res_list.status_code == 403

    # User 2 attempts to delete User 1's test
    res_delete = client.delete(
        f"/api/projects/{sample_project.id}/tests/{test_id}",
        headers=auth_headers_user2,
    )
    assert res_delete.status_code == 403
