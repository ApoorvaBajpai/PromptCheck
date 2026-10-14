# PromptCheck

> Continuous prompt regression testing, evaluation, and quality assurance platform for AI applications.

## Monorepo Architecture (Phase 0)

- **`backend/`**: FastAPI application with Python 3.12, SQLAlchemy 2, Alembic migrations, PostgreSQL connectivity, and `GET /healthz`.
- **`frontend/`**: Next.js 14 web interface built with TypeScript, Tailwind CSS, and shadcn/ui.
- **`cli/`**: Python CLI package built with Typer and Rich console tooling (`promptcheck`).
- **`action/`**: Reusable GitHub Action composite package for CI/CD pipelines.
- **`examples/qa-bot/`**: Example QA assistant with `promptcheck.yaml` test suite and bot implementation.
- **`docker-compose.yml`**: Docker service definitions for PostgreSQL, FastAPI backend, and Next.js frontend.
- **`.github/workflows/ci.yml`**: Complete GitHub Actions CI pipeline covering backend, CLI, and frontend linting, typing, migrations, and test suites.

## Quick Start

### 1. Environment Configuration
```bash
cp .env.example .env
```

### 2. Using Docker Compose
```bash
docker compose up -d
```

### 3. Local Development

#### Start PostgreSQL
```powershell
# Using installed local PostgreSQL:
pg_ctl -D "C:\Users\DELL\AppData\Local\Programs\PostgreSQL\data" -l logfile start
```

#### Run Backend
```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### Run Frontend
```bash
cd frontend
npm install
npm run dev
```

#### Run CLI
```bash
cd cli
pip install -e ".[dev]"
promptcheck ping --url http://localhost:8000
```

## Health Check
- URL: `http://localhost:8000/healthz`
- Method: `GET`
- Response:
```json
{
  "status": "healthy",
  "app": "PromptCheck API",
  "environment": "development",
  "database": "ok",
  "timestamp": "2026-10-14T19:00:00.000000+00:00"
}
```
