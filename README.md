# PromptCheck

> Continuous prompt regression testing, evaluation, and quality assurance platform for student and production LLM applications.

PromptCheck automates prompt regression testing against baseline versions, detects breaking behavioral regressions, scores quality using evaluators (exact match, regex, JSON schema, and LLM judge), and identifies flaky non-deterministic outputs.

---

## 1. System Architecture

```text
Browser Client / CLI
       │
       ▼
Next.js 14 Frontend (Port 3000)
       │ (internal proxy: BACKEND_INTERNAL_URL=http://backend:8000)
       ▼
FastAPI Backend (Port 8000)
  ├── ASGI Request Size Middleware (10MB limit)
  ├── Security & Auth (Bearer JWT, sliding-window rate limit, scoped stream tokens)
  ├── API Routers (Auth, Projects, Prompts, Test Cases, Runs)
  ├── Run Engine & Evaluators (Exact, Regex, JSON Schema, LLM Judge)
  ├── Output Cache (Project- & Config-scoped SHA-256)
  └── Durable Job Worker (PostgreSQL FOR UPDATE SKIP LOCKED + Heartbeat Reaper)
       │
       ▼
PostgreSQL 16 (Port 5432)
```

---

## 2. Core Technical Remediation & Features

1. **Production Dependencies**:
   - `httpx>=0.27.0` is declared in core production dependencies (`backend/pyproject.toml`).
   - Clean production installs do not depend on `[dev]` packages to start the server.

2. **Secrets & Encryption Security**:
   - `SECRET_KEY` and `ENCRYPTION_KEY` are strictly required in production (`ENVIRONMENT=production`).
   - Missing or default keys cause an immediate startup failure (fail-fast).
   - Silent derivation of Fernet keys from `SECRET_KEY` is completely removed.
   - Project Gemini API keys are encrypted at rest using AES-128-CBC/Fernet before persistence.

3. **Docker Networking & Internal Proxying**:
   - Next.js internal rewrites route `/api/:path*` to `BACKEND_INTERNAL_URL` (`http://backend:8000`).
   - Container-to-container traffic stays on Docker's internal network; browser calls continue using public origins.
   - Backend auto-migrates via Alembic on container boot and exposes `/healthz` and `/api/healthz`.

4. **Output Cache Scoping & Isolation**:
   - Cache keys incorporate: `project_id`, `model`, `system_instruction`, `temperature`, `top_p`, `max_output_tokens`, `response_mime_type`, and `rendered_prompt`.
   - Modifying any generation parameter or switching projects produces a cache miss.
   - Repeated test runs (`repeat_count > 1`) intentionally bypass the cache to measure non-determinism.

5. **PromptVersion Runtime Execution**:
   - Full generation configurations defined on `PromptVersion` are forwarded directly to the Gemini client execution layer.
   - Client defaults do not silently override stored prompt version parameters.

6. **Durable Run Execution & Recovery**:
   - Asynchronous in-process fire-and-forget tasks have been replaced with a durable background worker.
   - Jobs are claimed via PostgreSQL row-level locks: `SELECT ... FOR UPDATE SKIP LOCKED`.
   - Active runs update a `last_heartbeat_at` timestamp.
   - A background reaper detects stale runs (heartbeat older than 60s) and transitions them to `FAILED` with actionable recovery error messages.
   - Runs support `idempotency_key` preventing duplicate execution on retries.

7. **Repeated Execution & Flaky Test Detection**:
   - Supports `repeat_count >= 1`.
   - Each attempt is persisted with an explicit `repeat_index` under a composite unique constraint `(run_id, test_case_id, repeat_index)`.
   - Multi-attempt evaluation outcomes:
     - All attempts pass: **Passed (Stable)**
     - All attempts fail: **Failed (Stable)**
     - Mixed outcomes: **Flaky** (aggregates pass rate and score variance across attempts).

8. **LLM Judge Error Semantics**:
   - Distinguishes evaluator/provider failures (JSON malformed, provider 500s, schema violations) from genuine model quality test failures.
   - Evaluator failures set `status="error"` and `is_evaluator_error=True` rather than falsely scoring the student prompt as a quality failure.

9. **Hardened Authentication**:
   - Query-string JWT authentication (`?token=...`) is strictly rejected. Authenticated API access requires `Authorization: Bearer <token>`.
   - EventSource SSE streaming uses short-lived (60s) scoped tokens created via `POST /api/runs/{id}/stream-token`.
   - In-process sliding-window rate limiting protects `/api/auth/login` and `/api/auth/register` (10 attempts per minute).

10. **Request Size Protection**:
    - Global ASGI middleware (`RequestBodyLimitMiddleware`) rejects requests exceeding 10MB with HTTP 413.

---

## 3. Environment Variables

| Variable | Description | Required in Prod | Development Default |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Environment name (`development`, `production`) | No | `development` |
| `DEBUG` | Enable debug logging | No | `False` |
| `SECRET_KEY` | JWT signing secret (min 32 chars) | **Yes** (Fails fast if missing) | `promptcheck-secret` |
| `ENCRYPTION_KEY` | Fernet 32-byte url-safe base64 key | **Yes** (Fails fast if missing/invalid) | `t8ugVmp3vGlAT11bNiEaJELvyj-1f8qZkaQTDH1Au0E=` |
| `DATABASE_URL` | PostgreSQL connection string | **Yes** | `postgresql+psycopg2://postgres:postgres@localhost:5432/promptcheck` |
| `BACKEND_INTERNAL_URL` | URL used by Next.js server to call FastAPI | In Docker | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_API_URL` | Browser-accessible backend API origin | In Docker | `http://localhost:8000` |

### Key Generation Helper
```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 4. Quick Start

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone & copy environment variables
cp .env.example .env

# 2. Build and launch all services (PostgreSQL, Backend, Frontend)
docker compose up -d --build

# 3. Check logs
docker compose logs -f backend
```

Services will be running at:
- Frontend: `http://localhost:3000`
- Backend API Docs: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/healthz` (and `http://localhost:3000/api/healthz`)

---

### Option B: Local Manual Development

#### 1. Start PostgreSQL
Ensure PostgreSQL 16 is running with a database named `promptcheck`:
```bash
createdb -U postgres promptcheck
```

#### 2. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

#### 4. CLI
```bash
cd cli
pip install -e ".[dev]"
promptcheck ping --url http://localhost:8000
```

---

## 5. Running Tests & Quality Gates

```bash
# 1. Backend test suite (106 tests)
pytest backend/tests/ -v

# 2. Hardened security & reliability test suite
pytest backend/tests/test_hardened_features.py -v

# 3. CLI test suite
pytest cli/tests/ -v

# 4. Code quality & linting
ruff check backend/ cli/

# 5. Static type checking
mypy backend/app cli/promptcheck_cli

# 6. Frontend type check & production build
cd frontend && npm run build
```

---

## 6. Current Deployment Limitations

To maintain architectural transparency:

1. **Single-Host Background Worker**:
   - The queue worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`. While reliable across crashes and service restarts on a single node, multi-node deployments with high concurrency would benefit from Celery or a distributed broker (Redis/SQS).
2. **In-Memory Rate Limiting**:
   - The authentication rate limiter uses an in-memory sliding window per API process. When scaled across multiple distinct uvicorn workers or containers behind a load balancer, rate limits are enforced per-instance rather than globally. A Redis-backed token bucket would be required for clustered rate limiting.
3. **Model Generation Streaming**:
   - Test runs currently execute asynchronously and publish SSE progress events at the test result level. Streaming individual tokens from Gemini during test execution is not currently implemented.
