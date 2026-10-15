# PromptCheck Repository Audit (PHASE A)

**Date**: 2026-10-15  
**Auditor**: Senior Backend / Full-Stack Engineer  
**Status**: AUDIT COMPLETE — REMEDIATION IN PROGRESS

---

## 1. Executive Summary

A comprehensive technical audit of the PromptCheck codebase was conducted across backend, frontend, database models, migrations, API routes, authentication, Gemini client, run execution engine, evaluator framework, regression engine, caching, Docker, and CI/CD.

Key findings:
- **Test suite**: 60 passed, 23 errors. Errors are caused by test fixtures committing directly to the database via API endpoints without transaction isolation or cleanup, violating the unique constraint on `users.email`.
- **Static Analysis**: 3 Ruff lint errors (unused imports and formatting) and 1 Mypy error in `backend/app/api/auth.py`.
- **Production Dependencies**: `httpx` is missing from `[project.dependencies]` in `pyproject.toml` despite being imported by `backend/app/engine/client.py`.
- **Security & Secrets**: Insecure default secret keys and Fernet encryption keys are hardcoded in `config.py`. Fernet initialization silently falls back to a derived key rather than failing fast.
- **Docker Networking**: `frontend/next.config.mjs` hardcodes `http://127.0.0.1:8000`, which fails inside Docker containers.
- **Cache Correctness**: Cache keys do not include `project_id`, system instructions, or generation parameters, allowing cross-project cache leaks.
- **Run Engine & Flakiness**: `RunResult` has a uniqueness constraint on `(run_id, test_case_id)` with no `repeat_index`, preventing repeated test executions and flakiness analysis. Background workers are not started on API startup, and `Idempotency-Key` is ignored.
- **LLM Judge**: Evaluator parses boolean using `bool(parsed.get("passed"))`, causing `"false"` strings to evaluate to `True`.

---

## 2. Detailed Audit Findings

### Issue 1: Missing Production Dependency (`httpx`)
- **Affected Files**: `backend/pyproject.toml`, `backend/app/engine/client.py`
- **Severity**: P0 (Critical)
- **Reproduction/Evidence**: `client.py` imports `httpx`. In `pyproject.toml`, `httpx>=0.27.0` is listed solely under `[project.optional-dependencies] dev`. In a production Docker build (`pip install .`), `httpx` is not installed, causing `ModuleNotFoundError: No module named 'httpx'` upon model execution.
- **Proposed Fix**: Move `httpx>=0.28.0` to `dependencies` in `backend/pyproject.toml`.

---

### Issue 2: Insecure Secret & Encryption Defaults & Silent Key Derivation
- **Affected Files**: `backend/app/config.py`, `backend/app/core/security.py`, `.env.example`
- **Severity**: P0 (Critical)
- **Reproduction/Evidence**:
  - `config.py` hardcodes default secrets: `secret_key = "promptcheck-insecure-dev-secret-key..."` and `encryption_key = "t8ugVmp3vGlAT11bNiEaJELvyj-1f8qZkaQTDH1Au0E="`.
  - In `security.py`, `_get_fernet()` catches any exception on invalid key and silently derives a key from `secret_key` via SHA-256 instead of failing fast.
  - Production mode does not fail fast when secrets are missing or default.
- **Proposed Fix**:
  - Implement strict validation in `Settings`: in production (`ENVIRONMENT=production`), require strong, non-default `SECRET_KEY` and valid Fernet `ENCRYPTION_KEY`.
  - Remove silent key derivation in `_get_fernet()`; raise a clear, explicit error on invalid Fernet key.
  - Ensure secrets are never logged or returned in responses or exception details.

---

### Issue 3: Hardcoded Loopback in Docker Networking
- **Affected Files**: `frontend/next.config.mjs`, `docker-compose.yml`, `frontend/Dockerfile`
- **Severity**: P0 (Critical)
- **Reproduction/Evidence**:
  - `next.config.mjs` sets destination `http://127.0.0.1:8000/api/:path*`.
  - Inside a Docker container, `127.0.0.1:8000` refers to the container itself, not the backend service.
  - `docker-compose.yml` provides `NEXT_PUBLIC_API_URL: http://localhost:8000`, but inter-container SSR or proxy calls fail.
- **Proposed Fix**:
  - Support `INTERNAL_API_URL` or `BACKEND_INTERNAL_URL` (defaulting to `http://backend:8000` in Docker Compose and `http://127.0.0.1:8000` in local dev).
  - Update `next.config.mjs` and `docker-compose.yml` to use configurable backend internal URLs.

---

### Issue 4: Authentication Hardening (Query Token & HttpOnly Cookies)
- **Affected Files**: `backend/app/api/deps.py`, `backend/app/api/auth.py`, `frontend/src/lib/api.ts`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `deps.py` accepts `token_query: str | None = Query(None, alias="token")` for any endpoint, leaking tokens into server access logs, browser history, and HTTP referrers.
  - JWT token is stored in `localStorage` in the frontend.
  - SSE streaming uses query string or requires token in URL.
- **Proposed Fix**:
  - Migrate authentication support to secure HttpOnly cookies (with fallback to Bearer header for CLI/API clients).
  - Restrict query-string tokens; replace with short-lived (e.g. 60s) single-use stream tokens specifically for SSE `/api/runs/{id}/stream`.
  - Enforce strict project ownership checks across all routes.

---

### Issue 5: Missing Rate Limiting on Authentication Endpoints
- **Affected Files**: `backend/app/api/auth.py`, `backend/app/main.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `/api/auth/login` and `/api/auth/register` have no rate limiting, allowing unlimited automated credential attacks.
- **Proposed Fix**:
  - Add an in-memory sliding window or token-bucket rate limiter for auth routes with clear documentation of prototype bounds, returning HTTP 429 upon threshold breach.

---

### Issue 6: Gemini API Key Validation Missing
- **Affected Files**: `backend/app/api/projects.py`, `backend/app/engine/client.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `POST /api/projects/{id}/api-key` blindly encrypts and stores any string without making a test request to Gemini.
  - No `PUT /api/projects/{id}/api-key` endpoint.
  - No differentiation between invalid key, quota exhaustion (429), and network timeout.
- **Proposed Fix**:
  - Add API key validation via a lightweight test request (`countTokens` or 1-token probe).
  - Separate invalid key (HTTP 400/401) from quota exhaustion (do not reject key as invalid if quota is exhausted).
  - Never log or expose raw keys in errors or responses.
  - Support both `PUT` and `POST` for `/{project_id}/api-key`.

---

### Issue 7: Prompt Version & Gemini Execution Configuration
- **Affected Files**: `backend/app/models/prompt.py`, `backend/app/schemas/prompt.py`, `backend/app/engine/runner.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `PromptVersion` only stores `content`. It lacks `model`, `system_instruction`, `temperature`, `top_p`, `max_output_tokens`, `response_mime_type`.
  - `runner.py` hardcodes default `gemini-2.5-flash`.
- **Proposed Fix**:
  - Add configuration fields to `PromptVersion` (and migration).
  - Persist and reconstruct the exact model parameters per run.

---

### Issue 8: Output Cache Flaws & Cross-Project Leakage
- **Affected Files**: `backend/app/engine/runner.py`, `backend/app/models/run.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `_compute_cache_key(model, rendered_prompt)` does not include `project_id`, system instruction, or generation config.
  - Query filters only by `cache_key`, allowing Project A to read outputs cached by Project B.
  - No TTL / expiration check.
  - Repeated executions for flakiness analysis always hit the cache instead of bypassing it.
- **Proposed Fix**:
  - Update cache key to include `project_id`, `model`, `system_instruction`, `temperature`, and rendered prompt hash.
  - Scope cache lookup strictly to `project_id`.
  - Support cache expiration TTL and cache bypass option (`enable_cache=False` or bypass flag for repeated flakiness tests).

---

### Issue 9: Durable Run Execution, Concurrency & Idempotency
- **Affected Files**: `backend/app/api/runs.py`, `backend/app/engine/worker.py`, `backend/app/main.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `create_run_for_project` triggers execution via `loop.create_task(...)` inside the API process.
  - `worker_instance` is never started on application startup.
  - `Idempotency-Key` header is ignored.
  - Concurrent active runs for the same project are not prevented.
- **Proposed Fix**:
  - Support `Idempotency-Key` header on `POST /api/projects/{id}/runs` to return existing run if duplicate key is received.
  - Guard against multiple active running runs per project if configured.
  - Wire background worker startup/shutdown into FastAPI lifespan.
  - Implement SKIP LOCKED queue claiming and heartbeat reaper recovery.

---

### Issue 10: Repeat Execution / Flakiness Missing Schema Support
- **Affected Files**: `backend/app/models/run.py`, `backend/app/engine/runner.py`, `backend/app/engine/regression.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `run_results` table has `UniqueConstraint("run_id", "test_case_id")`.
  - When `repeat_count > 1`, inserting the second result violates this unique constraint.
- **Proposed Fix**:
  - Add `repeat_index` (default 0) to `RunResult`.
  - Change unique constraint to `("run_id", "test_case_id", "repeat_index")`.
  - Add `repeat_count` to `Run`.
  - Execute test cases `repeat_count` times (bypassing cache) and compute pass rates and flakiness.

---

### Issue 11: LLM-as-Judge Insecure Boolean & Schema Validation
- **Affected Files**: `backend/app/evaluators/llm_judge.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - `passed_val = bool(parsed.get("passed", False))` evaluates `"false"` to `True`.
  - Score is not validated to ensure `0.0 <= score <= 1.0` or to reject `NaN`/`inf`.
- **Proposed Fix**:
  - Define strict Pydantic model (`JudgeOutputSchema`) requiring strict boolean `passed: bool`, float `score: float = Field(ge=0.0, le=1.0)`, and string `reason`.
  - Reject `NaN`/`inf` and string booleans safely.
  - Fail safely on malformed JSON or schema validation errors after retry.

---

### Issue 12: Evaluator Robustness
- **Affected Files**: `backend/app/evaluators/json_schema.py`, `backend/app/evaluators/regex.py`, `backend/app/evaluators/semantic.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - Regex evaluator lacks safeguards against invalid regex syntax or flag errors.
  - JSON evaluator needs clean markdown fence stripping and strict schema validation.
  - Semantic evaluator must handle embedding API errors gracefully without failing silently.
- **Proposed Fix**:
  - Validate and normalize inputs across all evaluators with comprehensive edge-case handling.

---

### Issue 13: Test Case Import Security & Limits
- **Affected Files**: `backend/app/api/test_cases.py`
- **Severity**: P1 (High)
- **Reproduction/Evidence**:
  - No file size limit (reads unbounded `await file.read()`).
  - No row count limit or max test case limit per project.
  - No schema validation before insertion (inserts invalid data without row-level reporting).
  - No protection against CSV formula injection (`=`, `+`, `-`, `@`).
- **Proposed Fix**:
  - Impose upload size limit (e.g. 5MB) and row count limit (e.g. 500 rows).
  - Validate each row using `TestCaseCreate` schema and return row-level errors.
  - Sanitize exported CSV data against formula injection.

---

### Issue 14: Test Fixture DB Isolation & Lint/Type Cleanliness
- **Affected Files**: `backend/tests/conftest.py`, `backend/app/api/auth.py`, `backend/app/main.py`
- **Severity**: P2 (Medium)
- **Reproduction/Evidence**:
  - `conftest.py` transaction rollback fails because API endpoints call `db.commit()`, committing test users permanently to PostgreSQL and failing subsequent tests with `UniqueViolation`.
  - 3 Ruff lint errors and 1 Mypy error currently present.
- **Proposed Fix**:
  - Use table truncation or savepoint-based nested transactions in `conftest.py` so tests cleanly isolate.
  - Fix lint and Mypy typing issues.

---

### Issue 15: Demo Credentials in Production Frontend
- **Affected Files**: `frontend/src/app/login/page.tsx`
- **Severity**: P2 (Medium)
- **Reproduction/Evidence**:
  - State defaults `email` and `password` to `user1@example.com` and `password123`.
- **Proposed Fix**:
  - Keep default inputs empty in production; restrict demo auto-fill to explicit demo button with clear indicators.
