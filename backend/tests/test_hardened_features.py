import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.auth import AuthRateLimiter
from app.engine.client import FakeGeminiClient
from app.engine.runner import compute_output_cache_key
from app.evaluators.json_schema import JsonSchemaEvaluator
from app.evaluators.llm_judge import LLMJudgeEvaluator, StrictJudgeOutput
from app.evaluators.regex import RegexEvaluator


# 1. LLM-as-Judge Strict Validation & Adversarial Tests
def test_llm_judge_strict_schema_adversarial():
    """Verify that StrictJudgeOutput strictly rejects type coercion such as 'false' or numbers for booleans."""
    # Valid
    valid = StrictJudgeOutput(passed=True, score=1.0, reason="Looks great")
    assert valid.passed is True
    assert valid.score == 1.0

    # Adversarial: "false" string for boolean should fail strict bool validation
    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": "false", "score": 0.5, "reason": "bad"})

    # Adversarial: integer for boolean (e.g. 1 or 0)
    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": 1, "score": 1.0, "reason": "bad"})

    # Adversarial: score > 1.0 or < 0.0
    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": True, "score": 900, "reason": "bad"})

    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": True, "score": -0.1, "reason": "bad"})

    # Adversarial: NaN or infinity
    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": True, "score": float("nan"), "reason": "bad"})

    with pytest.raises(ValidationError):
        StrictJudgeOutput.model_validate({"passed": True, "score": float("inf"), "reason": "bad"})


@pytest.mark.asyncio
async def test_llm_judge_evaluator_adversarial_handling():
    """Verify LLMJudgeEvaluator fails safely when model returns malformed or adversarial JSON."""
    # Client returning string "false" in JSON
    client = FakeGeminiClient()
    client.set_judge_response('{"passed": "false", "score": 0.5, "reason": "should fail"}')
    evaluator = LLMJudgeEvaluator()
    config = {
        "rubric": "Be helpful",
        "threshold": 0.5,
    }
    res = await evaluator.evaluate(
        actual_output="Why did the chicken cross the road?",
        config=config,
        client=client,
    )
    # Must fail safely with clear error message, not silently coerced to passed=True
    assert res.passed is False
    assert "strict validation" in res.reason.lower() or "validation error" in res.reason.lower()


# 2. Output Cache Key Correctness Tests
def test_output_cache_key_determinism_and_scoping():
    """Verify all inputs affecting generation alter the cache key."""
    base_key = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-flash",
        system_instruction="You are helpful.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )

    # 1. Same inputs -> identical key
    same_key = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-flash",
        system_instruction="You are helpful.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )
    assert base_key == same_key

    # 2. Different project -> different key
    diff_project = compute_output_cache_key(
        project_id=2,
        model="gemini-1.5-flash",
        system_instruction="You are helpful.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )
    assert base_key != diff_project

    # 3. Different model -> different key
    diff_model = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-pro",
        system_instruction="You are helpful.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )
    assert base_key != diff_model

    # 4. Different system instruction -> different key
    diff_sys = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-flash",
        system_instruction="You are a pirate.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )
    assert base_key != diff_sys

    # 5. Different temperature -> different key
    diff_temp = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-flash",
        system_instruction="You are helpful.",
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Hello world",
    )
    assert base_key != diff_temp

    # 6. Different prompt -> different key
    diff_prompt = compute_output_cache_key(
        project_id=1,
        model="gemini-1.5-flash",
        system_instruction="You are helpful.",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=1000,
        response_mime_type="text/plain",
        rendered_prompt="Goodbye world",
    )
    assert base_key != diff_prompt


# 3. Auth Rate Limiter In-Process Sliding Window Tests
def test_auth_rate_limiter():
    """Verify that the auth rate limiter allows up to limit requests and throttles subsequent ones."""
    limiter = AuthRateLimiter(max_requests=5, window_seconds=60.0)
    key = "test_ip_client_unique_1"
    # Should allow 5 requests
    for _ in range(5):
        limiter.check(key)

    # 6th request must raise 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(key)
    assert exc_info.value.status_code == 429
    assert "Too many authentication attempts" in exc_info.value.detail


# 4. Evaluator Robustness (Regex, JSON Schema)
@pytest.mark.asyncio
async def test_regex_evaluator_robustness():
    """Verify regex evaluator handles invalid regex gracefully."""
    evaluator = RegexEvaluator()
    res = await evaluator.evaluate(
        actual_output="some output",
        config={"pattern": "[unclosed-bracket"},
    )
    assert res.passed is False
    assert "Invalid regular expression" in res.reason


@pytest.mark.asyncio
async def test_json_schema_markdown_fences():
    """Verify JSON schema evaluator strips markdown fences safely and validates schemas."""
    evaluator = JsonSchemaEvaluator()
    config = {
        "schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    }

    # Valid JSON inside markdown fences
    fenced = "```json\n{\"name\": \"Alice\"}\n```"
    res = await evaluator.evaluate(actual_output=fenced, config=config)
    assert res.passed is True

    # Invalid JSON inside fences
    bad_json = "```json\n{name: Alice}\n```"
    res_bad = await evaluator.evaluate(actual_output=bad_json, config=config)
    assert res_bad.passed is False
    assert "not valid JSON" in res_bad.reason or "Invalid JSON" in res_bad.reason


# 5. Run Idempotency Key & Concurrency Guard Tests
def test_run_idempotency_key(client, auth_headers_user1, sample_project, db_session):
    """Verify that submitting duplicate POST /runs with same Idempotency-Key returns original run."""
    from app.models.prompt import Prompt, PromptVersion
    from app.models.test_case import TestCase

    prompt = Prompt(project_id=sample_project.id, name="Idempotent Prompt")
    db_session.add(prompt)
    db_session.flush()

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        content="Hello {{ name }}",
        content_hash="idem123",
    )
    db_session.add(version)
    db_session.flush()

    tc = TestCase(
        project_id=sample_project.id,
        name="TC1",
        inputs={"name": "Bob"},
        assertions=[],
    )
    db_session.add(tc)
    db_session.commit()

    idempotency_headers = {**auth_headers_user1, "Idempotency-Key": "unique-idemp-key-999"}

    # First request
    res1 = client.post(
        f"/api/projects/{sample_project.id}/runs?auto_execute=false",
        headers=idempotency_headers,
        json={"prompt_version_id": version.id},
    )
    assert res1.status_code == 201
    run1 = res1.json()

    # Second duplicate request with identical Idempotency-Key
    res2 = client.post(
        f"/api/projects/{sample_project.id}/runs?auto_execute=false",
        headers=idempotency_headers,
        json={"prompt_version_id": version.id},
    )
    assert res2.status_code in (200, 201)
    run2 = res2.json()

    assert run1["id"] == run2["id"]


def test_concurrent_run_conflict_guard(client, auth_headers_user1, sample_project, db_session):
    """Verify that starting a new run when an active run is executing raises 409 Conflict."""
    from app.models.prompt import Prompt, PromptVersion
    from app.models.run import Run

    prompt = Prompt(project_id=sample_project.id, name="Concurrency Prompt")
    db_session.add(prompt)
    db_session.flush()

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        content="Testing",
        content_hash="conc123",
    )
    db_session.add(version)
    db_session.flush()

    # Put an existing run into running state
    running_run = Run(
        project_id=sample_project.id,
        prompt_version_id=version.id,
        status="running",
    )
    db_session.add(running_run)
    db_session.commit()

    # Attempt to start another run
    res = client.post(
        f"/api/projects/{sample_project.id}/runs?auto_execute=false",
        headers=auth_headers_user1,
        json={"prompt_version_id": version.id},
    )
    assert res.status_code == 409
    assert "already in progress" in res.json()["detail"] or "active run is currently executing" in res.json()["detail"]


# 6. Gemini API Key Validation Tests
def test_gemini_api_key_validation_invalid_and_quota(client, auth_headers_user1, sample_project, monkeypatch):
    """Verify PUT /projects/{id}/api-key handles invalid key vs quota exhausted cleanly."""
    from app.engine.client import FakeGeminiClient

    # 1. Invalid key failure -> 400
    fake_bad = FakeGeminiClient()
    fake_bad.set_invalid_api_key(True)
    monkeypatch.setattr("app.api.projects.get_gemini_client_for_key", lambda k: fake_bad)

    res_bad = client.put(
        f"/api/projects/{sample_project.id}/api-key",
        headers=auth_headers_user1,
        json={"api_key": "AIzaSyFakeInvalidKey123"},
    )
    assert res_bad.status_code == 400
    assert "Invalid Gemini API key" in res_bad.json()["detail"]

    # 2. Quota exceeded -> 200 with quota warning (key is saved, not rejected as invalid)
    fake_quota = FakeGeminiClient()
    fake_quota.set_quota_exhausted(True)
    monkeypatch.setattr("app.api.projects.get_gemini_client_for_key", lambda k: fake_quota)

    res_quota = client.put(
        f"/api/projects/{sample_project.id}/api-key",
        headers=auth_headers_user1,
        json={"api_key": "AIzaSyFakeValidKeyWithQuotaExhaustion"},
    )
    assert res_quota.status_code == 200
    data = res_quota.json()
    assert data["has_key"] is True
    assert "quota" in (data.get("warning") or "").lower()
    # Verify full plaintext key is NEVER leaked in response
    assert "AIzaSyFakeValidKeyWithQuotaExhaustion" not in str(data)
    assert data["masked_key"].startswith("AIzaSy...")


# 7. Evaluator Error Semantics vs Model Test Failure Distinction (Phase 8)
@pytest.mark.asyncio
async def test_llm_judge_error_vs_failure_distinction():
    """Verify evaluator distinguishes infrastructure/provider errors from model test failures."""
    evaluator = LLMJudgeEvaluator()
    config = {"rubric": "Answer must be polite."}

    # A. Missing client -> Evaluator/Config error
    res_no_client = await evaluator.evaluate(actual_output="Hello", config=config, client=None)
    assert res_no_client.status == "error"
    assert res_no_client.is_evaluator_error is True
    assert res_no_client.details["error_type"] == "evaluator_error"

    # B. Provider API failure -> Provider error
    failing_client = FakeGeminiClient()
    failing_client.set_fail_with_500(count=2)
    res_provider_err = await evaluator.evaluate(actual_output="Hello", config=config, client=failing_client)
    assert res_provider_err.status == "error"
    assert res_provider_err.is_evaluator_error is True
    assert res_provider_err.details["error_type"] == "provider_error"

    # C. Malformed JSON after retry -> Invalid judge response error
    bad_json_client = FakeGeminiClient()
    bad_json_client.set_judge_response("not a valid json output")
    res_json_err = await evaluator.evaluate(actual_output="Hello", config=config, client=bad_json_client)
    assert res_json_err.status == "error"
    assert res_json_err.is_evaluator_error is True
    assert res_json_err.details["error_type"] == "invalid_judge_response"

    # D. Model quality failure (Judge evaluated validly and rejected output)
    valid_rejection_client = FakeGeminiClient()
    valid_rejection_client.set_judge_response(
        {"passed": False, "score": 0.2, "reason": "Customer was insulted.", "details": {}}
    )
    res_fail = await evaluator.evaluate(actual_output="Get lost.", config=config, client=valid_rejection_client)
    assert res_fail.status == "failed"
    assert res_fail.is_evaluator_error is False
    assert res_fail.passed is False
    assert "insulted" in res_fail.reason


# 8. Query-String Token Authentication Rejection (Phase 10)
def test_query_string_token_rejected(client, user1):
    """Verify that passing tokens via ?token= query parameter is strictly rejected."""
    from app.core.security import create_access_token

    token = create_access_token(subject=user1.id)

    # 1. API route with ?token= must return 401
    res = client.get(f"/api/projects?token={token}")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]

    # 2. SSE stream with long-lived access token as stream_token must be rejected
    res_stream = client.get(f"/api/runs/1/stream?stream_token={token}")
    assert res_stream.status_code in (401, 403)


# 9. Request Body Size Limit Middleware (Phase 11)
def test_request_body_size_limit_413(client):
    """Verify ASGI middleware rejects payloads exceeding maximum size with HTTP 413."""
    # Send request with oversized content-length header (> 10MB)
    res = client.post(
        "/api/projects",
        headers={"Content-Length": "15000000", "Content-Type": "application/json"},
        content=b"{}",
    )
    assert res.status_code == 413
    assert "Request body too large" in res.json()["detail"]


