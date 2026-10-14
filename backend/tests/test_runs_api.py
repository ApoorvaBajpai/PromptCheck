import asyncio

import httpx
import pytest

from app.models.prompt import Prompt, PromptVersion
from app.models.test_case import TestCase


def test_runs_api_lifecycle(client, auth_headers_user1, sample_project, db_session):
    # 1. Create prompt, version, and test cases
    prompt = Prompt(project_id=sample_project.id, name="Classifier")
    db_session.add(prompt)
    db_session.flush()

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        content="Classify text: {{ text }}",
        content_hash="h123",
    )
    db_session.add(version)
    db_session.flush()

    tc = TestCase(
        project_id=sample_project.id,
        name="Test 1",
        inputs={"text": "hello"},
        assertions=[],
    )
    db_session.add(tc)
    db_session.commit()

    # 2. Create Run via API (auto_execute=False for manual queue testing)
    res_create = client.post(
        f"/api/projects/{sample_project.id}/runs?auto_execute=false",
        headers=auth_headers_user1,
        json={"prompt_version_id": version.id},
    )
    assert res_create.status_code == 201
    run_data = res_create.json()
    assert run_data["status"] == "queued"
    assert run_data["total_tests"] == 1
    run_id = run_data["id"]

    # 3. List runs for project
    res_list = client.get(
        f"/api/projects/{sample_project.id}/runs",
        headers=auth_headers_user1,
    )
    assert res_list.status_code == 200
    assert any(r["id"] == run_id for r in res_list.json())

    # 4. Get run details
    res_get = client.get(f"/api/runs/{run_id}", headers=auth_headers_user1)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == run_id

    # 5. Cancel run
    res_cancel = client.post(f"/api/runs/{run_id}/cancel", headers=auth_headers_user1)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"


def test_runs_ownership_protection(
    client, auth_headers_user1, auth_headers_user2, sample_project, db_session
):
    prompt = Prompt(project_id=sample_project.id, name="Private Prompt")
    db_session.add(prompt)
    db_session.flush()
    version = PromptVersion(
        prompt_id=prompt.id, version_number=1, content="Test", content_hash="hash"
    )
    db_session.add(version)
    db_session.commit()

    # User 1 creates run
    res_create = client.post(
        f"/api/projects/{sample_project.id}/runs?auto_execute=false",
        headers=auth_headers_user1,
        json={"prompt_version_id": version.id},
    )
    run_id = res_create.json()["id"]

    # User 2 attempts to get run (Invariant 4)
    res_user2 = client.get(f"/api/runs/{run_id}", headers=auth_headers_user2)
    assert res_user2.status_code == 403

    # User 2 attempts to cancel run
    res_cancel = client.post(f"/api/runs/{run_id}/cancel", headers=auth_headers_user2)
    assert res_cancel.status_code == 403


@pytest.mark.asyncio
async def test_sse_stream_endpoint(client, auth_headers_user1, sample_project, db_session):
    prompt = Prompt(project_id=sample_project.id, name="SSE Prompt")
    db_session.add(prompt)
    db_session.flush()
    version = PromptVersion(
        prompt_id=prompt.id, version_number=1, content="Hi", content_hash="hash_sse"
    )
    db_session.add(version)
    db_session.flush()

    tc = TestCase(
        project_id=sample_project.id,
        name="SSE TC",
        inputs={"name": "Alice"},
        assertions=[],
        is_active=True,
    )
    db_session.add(tc)
    db_session.flush()
    db_session.commit()

    from app.engine.events import broadcaster
    from app.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res_create = await ac.post(
            f"/api/projects/{sample_project.id}/runs?auto_execute=false",
            headers=auth_headers_user1,
            json={"prompt_version_id": version.id},
        )
        assert res_create.status_code == 201, f"Failed: {res_create.status_code} {res_create.text}"
        run_id = res_create.json()["id"]

        async def cancel_later():
            await asyncio.sleep(0.05)
            await broadcaster.emit(run_id, "run_completed", {"run_id": run_id})

        emit_task = asyncio.create_task(cancel_later())

        async with ac.stream(
            "GET", f"/api/runs/{run_id}/stream", headers=auth_headers_user1
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            lines = []
            async for line in response.aiter_lines():
                if line:
                    lines.append(line)
                if any("event: connected" in line_item for line_item in lines) and any(
                    "event: run_completed" in line_item for line_item in lines
                ):
                    break

        await emit_task
