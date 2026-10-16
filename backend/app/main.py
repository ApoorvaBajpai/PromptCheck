from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.prompts import standalone_prompt_router
from app.api.runs import router as runs_router
from app.api.test_cases import router as test_cases_router
from app.api.test_cases import standalone_tests_router
from app.config import settings
from app.engine.worker import worker_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start durable background queue worker (skip in serverless environments)
    import os

    if not os.environ.get("VERCEL"):
        worker_instance.start()
    yield
    # Shutdown: Cleanly terminate worker tasks
    if not os.environ.get("VERCEL"):
        await worker_instance.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "PromptCheck API - Continuous prompt regression testing and quality evaluation platform"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum payload size at the ASGI layer before buffering into memory (Phase 11).
    Guards against denial-of-service attempts via unbounded request bodies.
    """

    def __init__(self, app, max_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large ({int(content_length)} bytes). Maximum allowed size is {self.max_bytes // (1024 * 1024)}MB."
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


# Enforce 10MB HTTP request body limit before route handlers
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=10 * 1024 * 1024)

# CORS configuration supporting cookies and credentials
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|frontend)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(prompts_router)
app.include_router(standalone_prompt_router)
app.include_router(test_cases_router)
app.include_router(standalone_tests_router)
app.include_router(runs_router)


@app.get("/", summary="Root endpoint")
def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
