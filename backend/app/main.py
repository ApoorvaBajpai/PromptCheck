from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router, standalone_prompt_router
from app.api.runs import router as runs_router
from app.api.test_cases import router as test_cases_router, standalone_tests_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "PromptCheck API - Continuous prompt regression testing and quality evaluation platform"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
