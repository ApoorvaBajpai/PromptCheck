from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_project
from app.core.security import decrypt_api_key, encrypt_api_key, mask_api_key
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    ProjectApiKeyIn,
    ProjectApiKeyOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _to_project_out(project: Project) -> ProjectOut:
    """Format Project response, masking the API key (Invariant 6)."""
    has_key = bool(project.encrypted_gemini_api_key)
    masked = None
    if has_key and project.encrypted_gemini_api_key:
        try:
            decrypted = decrypt_api_key(project.encrypted_gemini_api_key)
            masked = mask_api_key(decrypted)
        except Exception:
            masked = "****"

    return ProjectOut(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        has_api_key=has_key,
        masked_api_key=masked,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project owned by current user."""
    encrypted_key = None
    if project_in.gemini_api_key:
        encrypted_key = encrypt_api_key(project_in.gemini_api_key)

    project = Project(
        user_id=current_user.id,
        name=project_in.name,
        description=project_in.description,
        encrypted_gemini_api_key=encrypted_key,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_out(project)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all projects owned by the authenticated user."""
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [_to_project_out(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project: Project = Depends(get_user_project),
):
    """Get project details with ownership enforcement (Invariant 4)."""
    return _to_project_out(project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_update: ProjectUpdate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Update project details with ownership enforcement."""
    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description

    db.commit()
    db.refresh(project)
    return _to_project_out(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Delete a project and its associated resources."""
    db.delete(project)
    db.commit()
    return None


@router.post("/{project_id}/api-key", response_model=ProjectApiKeyOut)
def set_project_api_key(
    payload: ProjectApiKeyIn,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Set and encrypt Gemini API key at rest (Invariant 5 & 6)."""
    project.encrypted_gemini_api_key = encrypt_api_key(payload.api_key)
    db.commit()
    db.refresh(project)
    return ProjectApiKeyOut(
        has_key=True,
        masked_key=mask_api_key(payload.api_key),
    )


@router.get("/{project_id}/api-key", response_model=ProjectApiKeyOut)
def get_project_api_key_status(
    project: Project = Depends(get_user_project),
):
    """Check API key presence and view masked key (never plaintext)."""
    if not project.encrypted_gemini_api_key:
        return ProjectApiKeyOut(has_key=False, masked_key=None)

    try:
        decrypted = decrypt_api_key(project.encrypted_gemini_api_key)
        masked = mask_api_key(decrypted)
    except Exception:
        masked = "****"

    return ProjectApiKeyOut(has_key=True, masked_key=masked)


@router.delete("/{project_id}/api-key", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_api_key(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db),
):
    """Remove stored API key."""
    project.encrypted_gemini_api_key = None
    db.commit()
    return None
