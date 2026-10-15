import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/healthz", summary="Health check verifying service and database status")
@router.get("/api/healthz", summary="Health check verifying service and database status via API prefix")
def healthz(db: Session = Depends(get_db)):
    """Health check endpoint that verifies database connectivity."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": db_status,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
        )

    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": db_status,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
