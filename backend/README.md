# PromptCheck Backend

FastAPI service powering the PromptCheck API.

## Requirements
- Python 3.12+
- PostgreSQL

## Local Setup
```bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
